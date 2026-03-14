import tkinter as tk

class CoordinateFinder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("250x100")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        self.root.configure(bg="black")
        
        # Remove the Windows border so it mimics your overlay exactly
        self.root.overrideredirect(True)
        
        self.label = tk.Label(
            self.root, 
            text="Drag Me!", 
            font=("Consolas", 16, "bold"), 
            fg="#00FFFF", 
            bg="black"
        )
        self.label.pack(expand=True, fill="both", pady=(10, 0))
        
        self.help_label = tk.Label(
            self.root, 
            text="Click & Drag | Press ESC to close", 
            font=("Consolas", 8), 
            fg="gray", 
            bg="black"
        )
        self.help_label.pack(side="bottom", pady=(0, 5))

        # Mouse bindings for dragging
        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)
        
        # Keyboard binding to close
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
        self.drag_start_x = 0
        self.drag_start_y = 0

        self.update_display()
        self.root.mainloop()

    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def do_drag(self, event):
        # Calculate new absolute coordinates
        new_x = event.x_root - self.drag_start_x
        new_y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{new_x}+{new_y}")
        self.update_display()

    def update_display(self):
        # Get actual window position in the virtual display plane
        curr_x = self.root.winfo_x()
        curr_y = self.root.winfo_y()
        self.label.config(text=f"X: {curr_x} | Y: {curr_y}")

if __name__ == "__main__":
    CoordinateFinder()