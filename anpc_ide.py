import ctypes
import os
import re
import tkinter as tk

top = tk.Tk()


class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget
        
    def redraw(self, *args):
        '''redraw line numbers'''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True :
            dline= self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(28,y,anchor="ne", text=linenum, font = "Consolas 12")
            i = self.textwidget.index("%s+1line" % i)


class CustomText(tk.Text):

    _previous_text = ""

# Define colors for the syntax editor
    def _rgb(rgb):
        return "#%02x%02x%02x" % rgb

    _colors = {
        'normal': _rgb((234, 234, 234)),
        'keywords': _rgb((234, 95, 95)),
        'comments': _rgb((95, 234, 165)),
        'string': _rgb((234, 162, 95)),
        'function': _rgb((95, 211, 234)),
        'background': _rgb((42, 42, 42))
    }

    _repl = [
        ['(^| )(false|nil|true|and|or|if|else|then|for|while|define program|end|break|do|switch|exit)($| )', _colors['keywords']],
        ['".*?"', _colors['string']],
        ['\'.*?\'', _colors['string']],
        ['--.*?$', _colors['comments']]
    ]

    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)
        print(args)
        print(kwargs)

        self._font = kwargs['font']

        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)
        self.bind('<KeyRelease>', self._check_and_repaint)

    def _proxy(self, *args):
        # let the actual widget perform the requested action
        cmd = (self._orig,) + args
        result = self.tk.call(cmd)

        # generate an event if something was added or deleted,
        # or the cursor position changed
        if (args[0] in ("insert", "replace", "delete") or 
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] == ("xview", "moveto") or
            args[0:2] == ("xview", "scroll") or
            args[0:2] == ("yview", "moveto") or
            args[0:2] == ("yview", "scroll")
        ):
            self.event_generate("<<Change>>", when="tail")

        # return what the actual widget returned
        return result
    
    def _check_and_repaint(self, event=None):
        if self.get('1.0', tk.END) == self._previous_text:
            return

        for tag in self.tag_names():
            self.tag_remove(tag, '1.0', 'end')

        i = 0
        for pattern, color in self._repl:
            for start, end in self._search_re(pattern, self.get('1.0', tk.END)):
                self.tag_add(f'{i}', start, end)
                self.tag_config(f'{i}', foreground = color)
                i += 1

        self._previous_text = self.get('1.0', tk.END)

    def _search_re(self, pattern, text, groupid = 0):
        matches = []

        text = text.splitlines()
        for i, line in enumerate(text):
            for match in re.finditer(pattern, line):
                matches.append((f"{i + 1}.{match.start()}", f"{i + 1}.{match.end()}"))

        return matches

class TextEditor(tk.Frame):

    def _rgb(rgb):
        return "#%02x%02x%02x" % rgb

    _colors = {
        'normal': _rgb((234, 234, 234)),
        'keywords': _rgb((234, 95, 95)),
        'comments': _rgb((95, 234, 165)),
        'string': _rgb((234, 162, 95)),
        'function': _rgb((95, 211, 234)),
        'background': _rgb((42, 42, 42))
    }

    def __init__(self, *args, **kwargs):
        kwargs.remove('font')
        tk.Frame.__init__(self, *args, **kwargs)
        # self.text = CustomText(self,
        # background = self._colors['background'],
        # foreground = self._colors['normal'],
        # insertbackground = self._colors['normal'],
        # relief = tk.FLAT,
        # borderwidth = 30,
        # font = "Consolas 12",
        # wrap = "none")

        self.text = CustomText(self, *args, **kwargs)

        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.text.tag_configure("bigfont", font=("Helvetica", "24", "bold"))
        self.linenumbers = TextLineNumbers(self, width=30)
        self.linenumbers.attach(self.text)

        self.vsb.pack(side="right", fill="y")
        self.linenumbers.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

        self.text.insert("end", "one\ntwo\nthree\n")
        self.text.insert("end", "four\n",("bigfont",))
        self.text.insert("end", "five\n")

    def _on_change(self, event):
        self.linenumbers.redraw()


def main():
    # Main window size
    top.geometry("600x400")

    TextEditor(top, font = 'Consolas 12').pack(side="top", fill="both", expand=True)
    top.mainloop()

if __name__ == "__main__":
	main()