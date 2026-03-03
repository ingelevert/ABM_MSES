// Custom Canvas Module with background image support
class CanvasModule {
    constructor(canvas_width, canvas_height, grid_width, grid_height) {
        this.canvas_width = canvas_width;
        this.canvas_height = canvas_height;
        this.grid_width = grid_width;
        this.grid_height = grid_height;
        
        // Create canvas element
        this.canvas = document.createElement("canvas");
        this.canvas.width = canvas_width;
        this.canvas.height = canvas_height;
        this.canvas.style.border = "1px solid black";
        this.context = this.canvas.getContext("2d");
        
        // Background image
        this.backgroundImage = null;
        this.backgroundLoaded = false;
    }
    
    render(data) {
        const gw = this.grid_width;
        const gh = this.grid_height;
        const cw = this.canvas_width;
        const ch = this.canvas_height;
        const ctx = this.context;
        
        // Clear canvas
        ctx.clearRect(0, 0, cw, ch);
        
        // Draw background image if available and loaded
        if (data.background && !this.backgroundLoaded) {
            this.backgroundImage = new Image();
            this.backgroundImage.onload = () => {
                this.backgroundLoaded = true;
                this.redraw(data);
            };
            this.backgroundImage.src = data.background;
            return;
        }
        
        if (this.backgroundLoaded && this.backgroundImage) {
            ctx.drawImage(this.backgroundImage, 0, 0, cw, ch);
        }
        
        // Draw agents
        for (let layer in data) {
            if (layer === "background") continue;
            
            const portrayalLayer = data[layer];
            for (let i = 0; i < portrayalLayer.length; i++) {
                const p = portrayalLayer[i];
                
                if (p.Shape === "rect") {
                    ctx.fillStyle = p.Color;
                    ctx.fillRect(
                        p.x * (cw / gw),
                        ch - ((p.y + 1) * (ch / gh)),
                        (cw / gw),
                        (ch / gh)
                    );
                } else if (p.Shape === "circle") {
                    ctx.fillStyle = p.Color;
                    ctx.beginPath();
                    const cx = (p.x + 0.5) * (cw / gw);
                    const cy = ch - ((p.y + 0.5) * (ch / gh));
                    const r = p.r * (cw / gw);
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI);
                    ctx.fill();
                }
            }
        }
    }
    
    redraw(data) {
        this.render(data);
    }
    
    reset() {
        this.backgroundLoaded = false;
        this.backgroundImage = null;
    }
}
