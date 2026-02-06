# custom_dialog.py - Enhanced DialogBox with multi-line label support
# Extension to micro-gui DialogBox for Disobey Badge 2025

from gui.core.ugui import Window, Screen, ssd
from gui.core.colors import *
from gui.widgets.label import Label
from gui.widgets.buttons import Button

dolittle = lambda *_ : None


class CustomDialogBox(Window):
    """
    Enhanced DialogBox with support for multi-line labels (using \n),
    automatic centering, and better horizontal padding.
    
    Designed for badge connection dialogs - no close button, always centered.
    """
    
    def __init__(self, writer, row=20, col=20, *, elements, label=None,
                 bgcolor=DARKGREEN, buttonwidth=25, callback=dolittle, args=[]):

        def back(button, text):  # Callback for buttons
            Window.value(text)
            callback(Window, *args)
            Screen.back()

        # Handle multi-line labels
        label_lines = []
        if label is not None:
            label_lines = label.split('\n') if '\n' in label else [label]
        
        height = 80
        spacing = 5
        h_padding = 10  # Horizontal padding for left/right
        buttonwidth = max(max(writer.stringlen(e[0]) for e in elements) + 14, buttonwidth)
        buttonheight = max(writer.height, 15)
        nelements = len(elements)
        width = spacing + (buttonwidth + spacing) * nelements
        
        # Calculate width based on longest label line with horizontal padding
        if label_lines:
            max_label_width = max(writer.stringlen(line) for line in label_lines)
            width = max(width, max_label_width + 2 * spacing + 2 * h_padding)
        
        # Adjust height for multi-line labels
        if len(label_lines) > 1:
            # Add extra height for additional lines
            extra_height = (len(label_lines) - 1) * (writer.height + 2)
            height = max(height, 80 + extra_height)
        
        # Center dialog on screen if using default row/col position
        if row == 20 and col == 20:  # Default position
            row = (ssd.height - height) // 2
            col = (ssd.width - width) // 2
        
        super().__init__(row, col, height, width, bgcolor = bgcolor)

        col = spacing # Coordinates relative to window
        row = self.height - buttonheight - 10
        gap = 0
        if nelements > 1:
            gap = ((width - 2 * spacing) - nelements * buttonwidth) // (nelements - 1)
        
        # Create label widgets for each line
        if label_lines:
            label_row = 10
            # Calculate available width for labels (full width minus horizontal padding)
            label_width = width - 2 * h_padding
            for line in label_lines:
                r, c = self.locn(label_row, h_padding)
                # Create label with width, then set text value
                lbl = Label(writer, r, c, label_width, bgcolor = bgcolor, justify=Label.CENTRE)
                lbl.value(line)
                label_row += writer.height + 2  # Space between lines
        
        for text, color in elements:
            Button(writer, *self.locn(row, col), height = buttonheight, width = buttonwidth,
                   textcolor = BLACK, bgcolor = color,
                   fgcolor = color, bdcolor = color,
                   text = text, shape = RECTANGLE,
                   callback = back, args = (text,))
            col += buttonwidth + gap
