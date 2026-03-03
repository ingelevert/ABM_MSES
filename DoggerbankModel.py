from mesa import Agent, Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid

from PIL import Image
import numpy as np

class Fish(Agent):
    def __init__(self, model):
        super().__init__(model)
        # Each fish has its own random preferred location within Doggerbank for each run
        self.preferred_x = self.random.randint(35, 69)
        self.preferred_y = self.random.randint(55, 84)
        

    def reproduce(self):
        # Decreases as population approaches carrying capacity
        total_fish = self.model.fish_count
        carrying_capacity = self.model.FISH_CARRYING_CAPACITY
        
        if self.pos[0] in range(35, 70) and self.pos[1] in range(55, 85):
            reproduction_rate = 0.002 # Per time step a Higher reproduction rate in Doggerbank
        else:
            reproduction_rate = 0.001  # Per time step Lower reproduction rate outside

        # Logistic growth probability
        population_ratio = total_fish / carrying_capacity
        reproduction_probability = max(0.0, reproduction_rate * (1 - population_ratio))

        if self.random.random() < reproduction_probability:
            new_fish = Fish(self.model)
            self.model.grid.place_agent(new_fish, self.pos)

    def die(self):
        total_fish = self.model.fish_count
        carrying_capacity = self.model.FISH_CARRYING_CAPACITY
        population_ratio = total_fish / carrying_capacity
        
        # Base mortality increases as population approaches carrying capacity
        base_mortality_rate = 0.001
        mortality_rate = base_mortality_rate * population_ratio
        
        if self.random.random() < mortality_rate:
            self.model.grid.remove_agent(self)
            self.remove()

    def move(self):
        # Move to the favorable area (Doggerbank) if within the carrying capacity of the area, otherwise random movement
        # Each fish has its own preferred location within Doggerbank
        target = (self.preferred_x, self.preferred_y)
        
        # Check if not at preferred location
        if self.pos[0] != target[0] or self.pos[1] != target[1]:
            # Use cached doggerbank fish count (updated once per model step)
            doggerbank_fish = self.model.doggerbank_fish_count
            
            # Doggerbank capacity based on all 1050 tiles (20% of total capacity)
            doggerbank_capacity = self.model.FISH_CARRYING_CAPACITY * 0.2
            
            if doggerbank_fish < (doggerbank_capacity * 0.75):
                # Move towards preferred location
                new_x = self.pos[0] + (1 if self.pos[0] < target[0] else -1 if self.pos[0] > target[0] else 0) # type: ignore
                new_y = self.pos[1] + (1 if self.pos[1] < target[1] else -1 if self.pos[1] > target[1] else 0)
            else:
                # Doggerbank is full - random movement
                new_x = self.pos[0] + self.random.randint(-1, 1)
                new_y = self.pos[1] + self.random.randint(-1, 1)
            # Only move if destination is water
            if not self.model.is_land((new_x, new_y)):
                self.model.grid.move_agent(self, (new_x, new_y))
        else:
            # At preferred location - small random movement to stay in area
            new_x = self.pos[0] + self.random.randint(-1, 1)
            new_y = self.pos[1] + self.random.randint(-1, 1)
            # Keep within Doggerbank bounds
            new_x = max(35, min(69, new_x))
            new_y = max(55, min(84, new_y))
            # Only move if destination is water
            if not self.model.is_land((new_x, new_y)):
                self.model.grid.move_agent(self, (new_x, new_y))

    def step(self):
        if self.pos is None:
            return
        
        self.move()
        self.reproduce()
        self.die()

class Fisher(Agent):
    def __init__(self, model):
        super().__init__(model)
        self.fuel = self.random.randint(5000, 10000)  # Randomized starting fuel
        self.total_catch = 0
        self.profit = 0
        self.determined_fishing_direction = False
        self.target_fishing_pos = None
        self.memory_map = np.zeros((model.grid.height, model.grid.width), dtype=np.float32)  # Memory of expected catch
        self.learning_rate = 0.1  # For updating memory
        self.steps_without_catch = 0  # Tracks how long since last successful catch
        self.last_successful_pos = None  # Last position where fish was caught
        self.return_to_successful_pos = False  # Flag to return to successful spot after harbor

    def step(self):
        if self.pos is None:
            return
        elif self.fuel < 250 or self.total_catch >= getattr(self.model, "TAK", 10):
            self.harbor_behavior()
        else:
            self.move()

    def move(self):
        # Check if we have a target fishing position to move towards
        if self.determined_fishing_direction == True:
        
            # Move towards target fishing position
            target_x, target_y = self.target_fishing_pos
            new_x = self.pos[0] + (0 if self.pos[0] == target_x else 1 if self.pos[0] < target_x else -1)
            new_y = self.pos[1] + (0 if self.pos[1] == target_y else 1 if self.pos[1] < target_y else -1)
            
            # Clamp to grid bounds
            new_x = max(0, min(new_x, self.model.grid.width - 1))
            new_y = max(0, min(new_y, self.model.grid.height - 1))
            
            dest = (new_x, new_y)
            
            # Check if destination is land or protected
            if self.model.is_land(dest) or self.model.get_tile_type_protected(dest).get("no_fishing", False):
                # Try to go around: check adjacent cells that are water and not protected
                possible_steps = self.model.grid.get_neighborhood(
                    self.pos, moore=True, include_center=False
                )
                possible_steps = [
                    step for step in possible_steps
                    if not self.model.is_land(step) and not self.model.get_tile_type_protected(step).get("no_fishing", False)
                ]
                if possible_steps:
                    # Pick the step closest to target
                    def dist_to_target(p):
                        return abs(p[0] - target_x) + abs(p[1] - target_y)
                    possible_steps.sort(key=dist_to_target)
                    dest = possible_steps[0]
                else:
                    # No valid moves, stay in place
                    self.fuel -= 50
                    return
            
            self.model.grid.move_agent(self, dest)
            self.fuel -= 50
            
            # Check if reached target, then switch to normal fishing behavior
            if self.pos == self.target_fishing_pos:
                self.determined_fishing_direction = False
                self.target_fishing_pos = None
            return
        
        else:
            # Check if we've been unsuccessful for 10+ turns - go towards area around successful fishers
            if self.steps_without_catch >= 10:
                # Use cached successful fisher positions from model
                successful_fisher_positions = self.model.successful_fisher_positions
                
                if successful_fisher_positions:
                    # Pick closest successful fisher
                    best_target = None
                    min_dist = float('inf')
                    for sfp in successful_fisher_positions:
                        dist = abs(self.pos[0] - sfp[0]) + abs(self.pos[1] - sfp[1])
                        if dist < min_dist:
                            min_dist = dist
                            best_target = sfp
                    
                    if best_target is not None:
                        # Choose a random position within ±8 cells of successful fisher
                        offset_x = self.random.randint(-8, 8)
                        offset_y = self.random.randint(-8, 8)
                        target_x = best_target[0] + offset_x
                        target_y = best_target[1] + offset_y
                        
                        # Clamp to grid bounds
                        target_x = max(0, min(target_x, self.model.grid.width - 1))
                        target_y = max(0, min(target_y, self.model.grid.height - 1))
                        
                        # Move towards this target area
                        new_x = self.pos[0] + (0 if self.pos[0] == target_x else 1 if self.pos[0] < target_x else -1)
                        new_y = self.pos[1] + (0 if self.pos[1] == target_y else 1 if self.pos[1] < target_y else -1)
                        
                        new_x = max(0, min(new_x, self.model.grid.width - 1))
                        new_y = max(0, min(new_y, self.model.grid.height - 1))
                        
                        dest = (new_x, new_y)
                        
                        # Check if destination is valid
                        if not self.model.is_land(dest) and not self.model.get_tile_type_protected(dest).get("no_fishing", False):
                            self.model.grid.move_agent(self, dest)
                            self.fuel -= 50
                            self.catch_fish()
                            return
                        else:
                            # Try to go around obstacle
                            possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
                            valid_steps = [s for s in possible_steps if not self.model.is_land(s) and not self.model.get_tile_type_protected(s).get("no_fishing", False)]
                            if valid_steps:
                                # Pick step closest to target area
                                valid_steps.sort(key=lambda p: abs(p[0] - target_x) + abs(p[1] - target_y))
                                self.model.grid.move_agent(self, valid_steps[0])
                                self.fuel -= 50
                                self.catch_fish()
                                return
            
            # Normal fishing behavior - biased towards personal success
            possible_steps = self.model.grid.get_neighborhood(
                self.pos, moore=True, include_center=False)
            possible_steps = [
                step for step in possible_steps if not self.model.is_land(step) and not self.model.get_tile_type_protected(step).get("no_fishing", False)
            ]

            if not possible_steps:
                self.fuel -= 50
                self.catch_fish()
                return
        
            # Calculate attractiveness for each step
            attractiveness_values = []
            
            for step in possible_steps:
                x, y = step
                attractiveness = 0.0
                
                # Bias towards personal successful fishing spots
                if self.last_successful_pos is not None:
                    current_dist = abs(self.pos[0] - self.last_successful_pos[0]) + abs(self.pos[1] - self.last_successful_pos[1])
                    new_dist = abs(step[0] - self.last_successful_pos[0]) + abs(step[1] - self.last_successful_pos[1])
                    if new_dist < current_dist:
                        attractiveness += 5.0  # Strong bias towards successful spot
                    elif new_dist == current_dist:
                        attractiveness += 2.0
                
                # Consider personal memory
                personal_memory = self.memory_map[y, x]
                attractiveness += personal_memory * 2.0
                
                attractiveness_values.append(attractiveness)

            # Weighted random selection
            attr_array = np.array(attractiveness_values) + 0.1
            total = np.sum(attr_array)
            if total > 0:
                probabilities = attr_array / total
            else:
                probabilities = np.ones(len(possible_steps)) / len(possible_steps)
            
            chosen_index = np.random.choice(len(possible_steps), p=probabilities)
            chosen_step = possible_steps[chosen_index]
            
            self.model.grid.move_agent(self, chosen_step)
            self.fuel -= 50
            self.catch_fish()

    def catch_fish(self):    
        cell_contents = self.model.grid.get_cell_list_contents(self.pos)
        fish_in_cell = [agent for agent in cell_contents if isinstance(agent, Fish)]
        
        # Catch up to 3 fish per step if present
        to_catch = fish_in_cell[:3]
        for fish in to_catch:
            self.model.grid.remove_agent(fish)
            fish.remove()
            self.total_catch += 1
            self.model.total_catch += 1
            self.model.step_catch += 1
        
        if to_catch:
            # Update tracking
            x, y = self.pos
            self.memory_map[y, x] += 0.1
            self.model.fishing_history[y, x] += 1
            self.last_successful_pos = self.pos
            self.steps_without_catch = 0
        else:
            self.steps_without_catch += 1

    def _at_harbor(self):
        # True if the fisher is at or has reached the Netherlands coast (harbor area)
        if self.pos == (99, 0):
            return True
        # Also treat it as harbor if we're in the bottom-right quadrant and
        # the next step toward (99,0) would be land (i.e. we've hit the coast)
        harbor = (99, 0)
        next_x = self.pos[0] + (0 if self.pos[0] == harbor[0] else -1 if self.pos[0] > harbor[0] else 1)
        next_y = self.pos[1] + (0 if self.pos[1] == harbor[1] else -1 if self.pos[1] > harbor[1] else 1)
        next_x = max(0, min(next_x, self.model.grid.width - 1))
        next_y = max(0, min(next_y, self.model.grid.height - 1))
        # If surrounded only by land in the harbor direction, we've arrived at ze harbooor
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        water_toward_harbor = [
            s for s in neighbors
            if not self.model.is_land(s)
            and (abs(s[0] - harbor[0]) + abs(s[1] - harbor[1])) < (abs(self.pos[0] - harbor[0]) + abs(self.pos[1] - harbor[1]))
        ]
        return len(water_toward_harbor) == 0  # no water tiles closer to harbor = we're at ze harbor

    def harbor_behavior(self):
        if self._at_harbor():
            # Refuel and sell catch
            earned = self.total_catch * getattr(self.model, "FISH_PRICE", 10)
            self.profit += earned
            self.model.period_profit += earned
            self.fuel = 10000  # Refuel to full
            self.total_catch = 0
            # Choose new fishing direction
            self.choose_new_fishing_direction()
        
        else:
            # Move towards harbor
            harbor = (99, 0)
            new_x = self.pos[0] + (0 if self.pos[0] == harbor[0] else -1 if self.pos[0] > harbor[0] else 1)
            new_y = self.pos[1] + (0 if self.pos[1] == harbor[1] else -1 if self.pos[1] > harbor[1] else 1)
            new_x = max(0, min(new_x, self.model.grid.width - 1))
            new_y = max(0, min(new_y, self.model.grid.height - 1))
            
            dest = (new_x, new_y)
            
            # If next step is land, navigate around it else you hit the beach and can't get to harbor
            if self.model.is_land(dest):
                possible_steps = self.model.grid.get_neighborhood(
                    self.pos, moore=True, include_center=False
                )
                water_steps = [s for s in possible_steps if not self.model.is_land(s)]
                if water_steps:
                    def dist_to_harbor(p):
                        return abs(p[0] - harbor[0]) + abs(p[1] - harbor[1])
                    water_steps.sort(key=dist_to_harbor)
                    dest = water_steps[0]
                else:
                    # No water neighbours, we've hit the coast, treat as harbor
                    earned = self.total_catch * getattr(self.model, "FISH_PRICE", 10)
                    self.profit += earned
                    self.model.period_profit += earned
                    self.fuel = 10000
                    self.total_catch = 0
                    self.choose_new_fishing_direction()
                    return
            
            self.model.grid.move_agent(self, dest)
        
    def choose_new_fishing_direction(self):
        
        target_x, target_y = None, None
        
        if self.last_successful_pos is not None and self.steps_without_catch < 10:
            # Check if the position is still valid (water, not protected)
            lsp_x, lsp_y = self.last_successful_pos
            if not self.model.is_land(self.last_successful_pos) and not self.model.get_tile_type_protected(self.last_successful_pos).get("no_fishing", False):
                target_x, target_y = lsp_x, lsp_y
                self.return_to_successful_pos = True
        
        if target_x is None:
            self.return_to_successful_pos = False
            
            # Use cached successful fisher positions from model
            successful_fisher_positions = self.model.successful_fisher_positions
            
            if successful_fisher_positions:
                # Pick a successful fisher and target an area around them
                candidates = []
                attractiveness_values = []
                
                for sfp in successful_fisher_positions:
                    dist = abs(self.pos[0] - sfp[0]) + abs(self.pos[1] - sfp[1])
                    candidates.append(sfp)
                    # Prefer closer successful fishers
                    attractiveness = 10.0 / max(dist, 1)
                    attractiveness_values.append(attractiveness)
                
                if candidates:
                    attr_array = np.array(attractiveness_values) + 0.1
                    total = np.sum(attr_array)
                    probabilities = attr_array / total if total > 0 else np.ones(len(candidates)) / len(candidates)
                    chosen_index = np.random.choice(len(candidates), p=probabilities)
                    chosen_fisher_pos = candidates[chosen_index]
                    
                    # Add random offset of ±8 cells around the successful fisher
                    offset_x = self.random.randint(-8, 8)
                    offset_y = self.random.randint(-8, 8)
                    target_x = chosen_fisher_pos[0] + offset_x
                    target_y = chosen_fisher_pos[1] + offset_y
            
            if target_x is None:
                candidates = []
                attractiveness_values = []
                
                fish_hist_max = np.max(self.model.fishing_history)
                shared_max = fish_hist_max if fish_hist_max > 0 else 1
                mem_max = np.max(self.memory_map)
                personal_max = mem_max if mem_max > 0 else 1
                
                # Sample grid positions every 10 cells for efficiency, and calculate attractiveness based on shared fishing history and personal memory
                for x in range(0, self.model.grid.width, 10):
                    for y in range(0, self.model.grid.height, 10):
                        pos = (x, y)
                        if not self.model.is_land(pos) and not self.model.get_tile_type_protected(pos).get("no_fishing", False):
                            candidates.append(pos)
                            
                            attractiveness = 0.0
                            
                            # Consider shared fishing history
                            shared_history = self.model.fishing_history[y, x]
                            shared_normalized = shared_history / shared_max
                            attractiveness += shared_normalized * 5.0
                            
                            # Also value personal memory
                            personal_memory = self.memory_map[y, x]
                            personal_normalized = personal_memory / personal_max
                            attractiveness += personal_normalized * 2.0
                            
                            attractiveness_values.append(attractiveness)
                
                if not candidates:
                    # Fallback to random water position if no candidates
                    for _ in range(50):
                        target_x = self.random.randint(10, 90)
                        target_y = self.random.randint(10, 90)
                        if not self.model.is_land((target_x, target_y)):
                            break
                else:
                    # Weighted random selection based on attractiveness
                    attr_array = np.array(attractiveness_values) + 0.1
                    total = np.sum(attr_array)
                    if total > 0:
                        probabilities = attr_array / total
                    else:
                        probabilities = np.ones(len(candidates)) / len(candidates)
                    
                    chosen_index = np.random.choice(len(candidates), p=probabilities)
                    target_x, target_y = candidates[chosen_index]
        
        # Clamp to grid bounds
        target_x = max(0, min(target_x, self.model.grid.width - 1))
        target_y = max(0, min(target_y, self.model.grid.height - 1))
        
        # Set the target position and flag that we have a determined direction
        self.target_fishing_pos = (target_x, target_y)
        self.determined_fishing_direction = True

class DoggerbankModel(Model):
    # Class-level defaults for Solara visualization before instance creation
    steps = 0
    datacollector = None
    space = None
    grid = None  # Add grid as class attribute
    
    def __init__(self, n_fish=2000, n_fisher=50, width=100, height=100, fish_policy=True):
        # Initialize space first
        self.grid = MultiGrid(width, height, torus=False)
        self.space = self.grid  # Alias for Solara
        
        super().__init__()
        self.n_fish = n_fish
        self.n_fisher = n_fisher
        self._agent_id = 0
        self.steps = 0 
        self.FISH_CARRYING_CAPACITY = n_fish * 3  # Reduced K so fishing pressure matters more
        self.FISH_POLICY = fish_policy  # True = Doggerbank is protected; False = open fishing everywhere
        self.FISH_PRICE = 10
        self.TAK = 20  # Fishers stay at sea longer before returning to harbour
        self.total_catch = 0
        self.step_catch = 0  # Fish caught in the current step (used internally)
        self.period_profit = 0   # Profit accumulated over the current 200-step period
        self.season_profit = 0   # Profit recorded at the end of each 200-step period
        self.PERIOD_LENGTH = 200  # Steps per season
        # MSY = r * N * (1 - N/K), updated each step
        self.msy = 0
        
        # Cached fish counts (updated each step for performance)
        self.fish_count = n_fish
        self.doggerbank_fish_count = 0
        self.successful_fisher_positions = []  # Cached list of successful fisher positions
        
        # Fishing history map - tracks where fish have been caught (shared knowledge)
        self.fishing_history = np.zeros((height, width), dtype=np.float32)
        
        # Load land map from background image
        self.land_map = self.load_land_map('static/north_sea_overlay.png', width, height)

        self.tile_types_protected = {
            (x, y): {"type": "Doggerbank", "no_fishing": self.FISH_POLICY}
               for x in range(35, 70)
               for y in range(55, 85)
        }

        # Randomized placement of agents (only on water)
        for i in range(self.n_fish):
            fish = Fish(self)
            # Find a water position
            attempts = 0
            while attempts < 100:
                x = self.random.randrange(self.grid.width)
                y = self.random.randrange(self.grid.height)
                if not self.is_land((x, y)):
                    self.grid.place_agent(fish, (x, y))
                    break
                attempts += 1

        for i in range(self.n_fisher):
            fisher = Fisher(self)
            # Find a water position outside the Doggerbank MPA (x: 35-70, y: 55-85)
            attempts = 0
            while attempts < 200:
                x = self.random.randrange(self.grid.width)
                y = self.random.randrange(self.grid.height)
                if not self.is_land((x, y)) and (x, y) not in self.tile_types_protected:
                    self.grid.place_agent(fisher, (x, y))
                    break
                attempts += 1

        self.datacollector = DataCollector(
            model_reporters={
                "Fish": lambda m: m.fish_count,
                "Seasonal Profit": lambda m: m.season_profit,
                "Step Catch": lambda m: m.step_catch,
                "MSY": lambda m: m.msy,
            }
        )

    def load_land_map(self, image_path, width, height):
        """Load land map from image where opaque pixels are land"""
        try:
            img = Image.open(image_path)
            # Resize to match grid dimensions
            img = img.resize((width, height), Image.Resampling.NEAREST)
            img_array = np.array(img)
            
            # Create land map: True = land (opaque), False = water (transparent)
            if img.mode == 'RGBA':
                # Land where alpha > 128 (mostly opaque)
                land_map = img_array[:, :, 3] > 128
            else:
                # If no alpha channel, assume black pixels are land
                gray = np.mean(img_array[:, :, :3], axis=2)
                land_map = gray < 128
            
            # Flip vertically to match grid coordinates
            land_map = np.flipud(land_map)
            return land_map
        except Exception as e:
            print(f"Warning: Could not load land map: {e}")
            # Return empty land map
            return np.zeros((height, width), dtype=bool)
    
    def is_land(self, pos):
        """Check if a position is land"""
        x, y = pos
        if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
            return self.land_map[y, x]
        return True  # Out of bounds = land
    
    def get_tile_type_protected(self, pos):
        """Return tile info; no_fishing respects the current live FISH_POLICY value."""
        if pos in self.tile_types_protected:
            return {"type": "Doggerbank", "no_fishing": self.FISH_POLICY}
        return {"type": "open_water", "no_fishing": False}

    def next_id(self):
        self._agent_id += 1
        return self._agent_id

    def step(self):
        self.step_catch = 0
        # Compute MSY reference: theoretical max sustainable yield at current N
        # r*N*(1 - N/K) gives the logistic growth curve; peak at N=K/2
        r = 0.002 * 0.6 + 0.001 * 0.4  # weighted avg growth rate
        K = self.FISH_CARRYING_CAPACITY
        N = self.fish_count
        self.msy = r * N * (1 - N / K) if K > 0 else 0
        
        # Update doggerbank fish count and successful fisher cache before agents act
        self.doggerbank_fish_count = sum(
            1 for a in self.agents 
            if isinstance(a, Fish) and a.pos and 35 <= a.pos[0] < 70 and 55 <= a.pos[1] < 85
        )
        
        # Cache successful fisher positions (those who caught fish recently)
        self.successful_fisher_positions = [
            a.pos for a in self.agents 
            if isinstance(a, Fisher) and a.pos and a.steps_without_catch < 3
        ]
        
        # Mesa 3.x automatically steps all agents
        self.agents.shuffle_do("step")
        self.steps += 1  # Increment step counter
        # Refresh fish count after agents have acted so the graph reflects post-step population
        self.fish_count = sum(1 for a in self.agents if isinstance(a, Fish))
        # Every PERIOD_LENGTH steps, publish the accumulated profit and reset
        if self.steps % self.PERIOD_LENGTH == 0:
            self.season_profit = self.period_profit
            self.period_profit = 0
        else:
            self.season_profit = 0
        self.datacollector.collect(self)


def agent_draw(agent):
    if agent is None:
        return None

    from mesa.visualization.components.portrayal_components import AgentPortrayalStyle
    if isinstance(agent, Fish):
        return AgentPortrayalStyle(color="tab:blue", size=20, marker="o")
    elif isinstance(agent, Fisher):
        return AgentPortrayalStyle(color="tab:red", size=50, marker="^")  
    return AgentPortrayalStyle()


def make_land_overlay(model):
    """Return a post_process function that draws the land map on the matplotlib axes."""
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    import numpy as np

    def post_process(ax):
        try:
            # Build an RGBA image: land = dark brown, water = transparent
            h, w = model.land_map.shape
            rgba = np.zeros((h, w, 4), dtype=np.float32)
            land = model.land_map  # True where land
            rgba[land, 0] = 0.4   # R
            rgba[land, 1] = 0.3   # G
            rgba[land, 2] = 0.2   # B
            rgba[land, 3] = 0.75  # alpha
            # Draw Doggerbank reserve as green
            for x in range(35, 70):
                for y in range(55, 85):
                    if not model.land_map[y, x]:  # only water cells
                        rgba[y, x, 0] = 0.1
                        rgba[y, x, 1] = 0.6
                        rgba[y, x, 2] = 0.1
                        rgba[y, x, 3] = 0.35
            ax.imshow(rgba, origin='lower', extent=[0, w, 0, h],
                      aspect='auto', zorder=0, interpolation='nearest')
        except Exception as e:
            print(f'Land overlay error: {e}')

    return post_process


def run_visualization():
    from mesa.visualization import SolaraViz, make_space_component, make_plot_component
    
    # Model parameters for the UI
    model_params = {
        "n_fish": {
            "type": "SliderInt",
            "value": 100,
            "label": "Number of Fish",
            "min": 50,
            "max": 500,
            "step": 50,
        },
        "n_fisher": {
            "type": "SliderInt",
            "value": 30,
            "label": "Number of Fishers",
            "min": 10,
            "max": 100,
            "step": 10,
        },
        "fish_policy": {
            "type": "Checkbox",
            "value": True,
            "label": "Doggerbank MPA Protected",
        },
        "width": 100,
        "height": 100,
    }

    # Pass an initial model instance (not the class) so grid is never None
    initial_model = DoggerbankModel(n_fish=100, n_fisher=30, width=100, height=100, fish_policy=True)

    # Create the visualization
    page = SolaraViz(
        initial_model,
        components=[
            make_space_component(
                agent_portrayal=agent_draw,
                draw_grid=False,
                post_process=make_land_overlay(initial_model),
            ),
            make_plot_component(["Fish"]),
            make_plot_component(["Seasonal Profit"]),
            make_plot_component({"Step Catch": "tab:orange", "MSY": "tab:green"}),
        ],
        model_params=model_params,
        name="Doggerbank Model",
        play_interval=150,
    )
    
    return page

# For Solara to pick up
page = run_visualization()

# Run with: solara run DoggerbankModel.py