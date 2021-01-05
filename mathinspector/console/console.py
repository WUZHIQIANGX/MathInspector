"""
Math Inspector: a visual programming environment for scientific computing with python
Copyright (C) 2020 Matt Calhoun

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import tkinter as tk
import numpy as np
import inspect, __main__, sys, traceback, os, re, plot
from util import vdict, open_editor, BUTTON_RIGHT, BASEPATH
from doc import Help
from style import Color, TAGS
from code import InteractiveInterpreter
from types import CodeType
from widget import Text, Menu
from .prompt import Prompt, FONTSIZE
from .codeparser import CodeParser
from .builtin_print import builtin_print

RE_TRACEBACK = r"^()(Traceback \(most recent call last\))"
RE_FILEPATH = r"(File (\"(?!<).*\"))"
RE_INPUT = r"(File \"(<.*>)\")"
RE_LINE = r"((line [0-9]*))"
RE_IN = r"line ([0-9]*), in (.*)"

class Console(Text, InteractiveInterpreter):
	def __init__(self, app):	
		InteractiveInterpreter.__init__(self, vdict({
			"app": app,
			"plot": plot.plot
		}, setitem=self.setitem, delitem=self.delitem))

		self.frame = tk.Frame(app, 
			padx=16,
			pady=8,
			background=Color.DARK_BLACK)

		Text.__init__(self, self.frame,
			readonly=True, 
			background=Color.DARK_BLACK, 
			font="Menlo 15",
			padx=0,
			pady=0,
			wrap="word",
			cursor="arrow", 
			insertbackground=Color.DARK_BLACK)

		sys.displayhook = self.write
		sys.excepthook = self.showtraceback
		__builtins__["print"] = self.write		
		__builtins__["help"] = Help(app)
		__builtins__["clear"] = Clear(self)
		__builtins__["copyright"] = "Copyright (c) 2018-2021 Matt Calhoun.\nAll Rights Reserved."
		__builtins__["credits"] = "Created by Matt Calhoun.\nSee https://mathinspector.com for more information."
		__builtins__["license"] = License()

		self.app = app
		self.prompt = Prompt(self, self.frame)
		self.parse = CodeParser(app)
		self.buffer = []

		self.bind("<Key>", self._on_key_log)
		self.bind("<Configure>", self.prompt.on_configure_log)
		self.bind("<ButtonRelease-1>", self.on_click_log)
		self.pack(fill="both", expand=True)
		
		for i in ["error_file"]:
			self.tag_bind(i, "<Motion>", lambda event, key=i: self._motion(event, key))
			self.tag_bind(i, "<Leave>", lambda event, key=i: self._leave(event, key))
			self.tag_bind(i, "<Button-1>", lambda event, key=i: self._click(event, key))    

	def _init(self, event):
		self.config_count = self.config_count + 1 if hasattr(self, "config_count") else 1
		if self.config_count > 2:
			self.do_greet()
			self.prompt.place(width=self.winfo_width())
			self.bind("<Configure>", self.prompt.on_configure_log)
		
	def do_greet(self):
		self.write("Math Inspector 0.9.0 (Beta)\nType \"help\", \"copyright\", \"credits\", \"license\" for more information")	
		self.prompt()

	def setitem(self, key, value):
		if inspect.ismodule(value):
			self.app.modules[key] = value
		else:
			self.app.objects[key] = value

	def delitem(self, key, value):
		if inspect.ismodule(value):
			del self.app.modules[key]
		else:
			del self.app.objects[key]

	def synclocals(self):
		self.locals.store.update(self.app.objects.store)
		self.locals.store.update(self.app.modules.store)

	def eval(self, source):
		self.synclocals()
		return eval(source, self.locals)

	def push(self, s, filename="<input>", log=True):
		self.synclocals()
		source = "".join(self.buffer + [s])
		self.parse.preprocess(source)
		if source[:4] == "plot":
			self.prompt()
		did_compile = self.runsource(source, filename)
		
		if did_compile:
			self.buffer.append(s + "\n")
		else:
			self.parse(source)
			self.prompt.history.extend(s)
			self.buffer.clear()
		self.prompt()
	
	def runscript(self, source, filename="<input>", symbol="single"):
		lines = source.split("\n")
		for s in lines:
			self.push(s + "\n")
		self.push("\n", filename)

	def write(self, *args, syntax_highlight=False, tags=(), **kwargs):
		idx = self.index("insert")
		for r in args:
			if re.match(RE_TRACEBACK, str(r)):
				tags = ("red", *tags)
			
			if r is not None:
				if isinstance(r, Exception):
					builtin_print("\a")
					tags = tuple(list(tags) + ["red"])
				self.insert("end", str(r), tags, syntax_highlight=syntax_highlight)
				if len(args) > 1:
					self.insert("end", "\t")
		
		try:
			self.highlight(RE_FILEPATH, "error_file", idx)
			self.highlight(RE_INPUT, "purple", idx)
			self.highlight(RE_LINE, "blue", idx)
			self.highlight(RE_IN, "green", idx)
		except:
			pass

		if self.get("1.0", "end").strip():
			self.insert("end", "\n")
		self.see("end")
		self.prompt.move()

	def showtraceback(self, *args):
		sys.last_type, sys.last_value, last_tb = ei = sys.exc_info()
		sys.last_traceback = last_tb

		try:
			lines = traceback.format_exception(ei[0], ei[1], last_tb.tb_next)
			self.write(''.join(lines).rstrip(), tags="red")
			builtin_print ("\a")
			self.app.menu.setview("console", True)
		finally:
			last_tb = ei = None

	def clear(self):
		self.prompt.is_on_bottom = False
		self.delete("1.0", "end")
	
	def _on_key_log(self, event):
		result = self._on_key(event)
		if result:
			self.prompt.focus()
		return result

	def on_click_log(self, event):
		 if not self.tag_ranges("sel"):
		 	self.prompt.focus()

	def _on_button_right(self, event):
		option = []
		tag_ranges = self.tag_ranges("sel")
		if tag_ranges:
			option.extend([{
				"label": "Copy",
				"command": lambda: self.clipboard_append(self.get(*tag_ranges))
			}])

		self.menu.show(event, option + [{
			"label": "Clear Log",
			"command": clear
		}])


	def _click(self, event, tag):
		if not self.hover_range: return
		content = self.get(*self.hover_range)
		if tag == "error_file":
			open_editor(os.path.abspath(content[1:-1]))

class License:
	def __call__(self):
		help(os.path.join(BASEPATH, "LICENSE"))

	def __repr__(self):
		return """
Math Inspector: a visual programming environment for scientific computing

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Type license() to see the full license text
		"""

class Clear:
	def __init__(self, console):
		self.console = console
	
	def __call__(self):
		self.console.clear()
		self.console.prompt()
	
	def __repr__(self):
		self.console.clear()
		self.console.prompt()
		return ""				
