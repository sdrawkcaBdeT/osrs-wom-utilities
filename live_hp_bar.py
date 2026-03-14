import tkinter as tk
import requests

class LiveHPBar:
    def __init__(self):
        self.root = tk.Tk()
        
        # Sized for a sleek, modern HP bar
        self.width = 1900
        self.height = 30
        self.root.geometry(f"{self.width}x{self.height}+100+100")
        
        # Removes Windows borders and floats on top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")

        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg="black", highlightthickness=1, highlightbackground="#333333")
        self.canvas.pack(fill="both", expand=True)

        # Dragging logic
        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Start the high-speed loop
        self.update_loop()
        self.root.mainloop()

    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def do_drag(self, event):
        x = event.x_root - self.drag_start_x
        y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def update_loop(self):
        try:
            # Poll the local Flask server (extremely fast)
            resp = requests.get("http://127.0.0.1:5000/hp", timeout=0.1)
            data = resp.json()
            
            self.canvas.delete("all")
            
            if data.get("active"):
                curr = data.get("current", 0)
                maximum = data.get("max", 315)
                
                # Calculate pixel width of the green bar
                pct = max(0.0, min(1.0, curr / maximum))
                bar_w = int(self.width * pct)
                
                # Draw Red Background
                self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#8B0000", outline="")
                # Draw Green Foreground
                self.canvas.create_rectangle(0, 0, bar_w, self.height, fill="#00FF00", outline="")
                # Draw Text
                text = f"{curr} / {maximum}"
                self.canvas.create_text(self.width//2, self.height//2, text=text, fill="white", font=("Consolas", 12, "bold"))
            else:
                # Idle state (Invisible or minimal)
                self.canvas.create_text(self.width//2, self.height//2, text="AWAITING COMBAT", fill="gray", font=("Consolas", 10))
                
        except Exception as e:
            # Server not running or unreachable
            self.canvas.delete("all")
            self.canvas.create_text(self.width//2, self.height//2, text="DISCONNECTED", fill="red", font=("Consolas", 10))

        # Re-run this check every 100 milliseconds
        self.root.after(100, self.update_loop)

if __name__ == "__main__":
    LiveHPBar()