#!/usr/bin/env python
# -*- coding: utf-8 -*-
# date: 19.05.09
# author: sikmir

import Tkinter
from Tkinter import *
import string, os, traceback
import tkSimpleDialog
import re

packages = [
# -------command--------packet----------build----------description----------
        ["arp",         "arp", 		True, NORMAL, "arp table"],
        ["help",        "help",		True, NORMAL, "display all possible commands"],
        ["lspnp",       "lspnp",	True, NORMAL, "show list of plug and play devices"],
        ["mem",         "mem",		True, NORMAL, "read from memory or test memory"],
        ["mmu_probe",   "mmu_probe",	False, DISABLED, "mmu_probe"],
        ["ping",        "ping",		True, NORMAL, "test whether a particular host is reachable"],
        ["udpd",        "udpd",		True, NORMAL, "test udp socket"],
        ["wmem",        "wmem",		True, NORMAL, "write to memory"] ]

arch = [('sparc', 0), ('x86', 1)]
error_level, trace_level, warn_level, debug_level, test_system_level, leon3_level = (None, None, None, None, None, None)
root, menu_frame, info_frame = (None, None, None)
debug, release, simulation, docs = (None, None, None, None)
cmpl, trg, arc_v = (None, None, None)

def onPress(i):
    packages[i][2] = not packages[i][1]

def make_conf():
    build_shell()
    build_subdirs()
    build_makefile()

def build_shell():
    """generate src/conio/shell.inc and src/conio/tests.inc"""
    with open('src/conio/shell.inc', 'w+') as shell:
	shell.write("//Don't edit! shell.inc: auto-generated by configure.py\n\n")
	for test, pack, inc, status, desc in packages:
	    if inc == True:
		if test != "wmem":
		    shell.write("{\"" + test + "\", \"" + desc + "\", " + test + "_shell_handler},\n")
		else:
		    shell.write("{\"" + test + "\", \"" + desc + "\", " + test + "_shell_handler}\n")
    shell.close()
    with open('src/conio/tests.inc', 'w+') as test_include:
	test_include.write("//Don't edit! test.inc: auto-generated by configure.py\n\n")
	for test, pack, inc, status, desc in packages:
	    if inc == True:
		if test != "arp":
		    test_include.write("#include \"" + test + ".h\"\n")
		else:
		    test_include.write("#include \"" + test + "c.h\"\n")
    test_include.close()

def build_subdirs():
    """generate src/tests/subdirs"""
    with open('src/tests/subdirs', 'w+') as subdirs:
	subdirs.write("SUBDIRS:= \\\n")
	for test, pack, inc, status, desc in packages:
	    if inc == True:
		if pack != "wmem":
		    subdirs.write(str(pack) + " \\\n")
		else:
		    subdirs.write(str(pack) + " \n")
    subdirs.close()

def repl_arch(m):
    return "CPU_ARCH:= " + arch[arc_v.get()][0]

def repl_compil(m):
    return "CC_PACKET:= " + cmpl.get()

def repl_target(m):
    return "TARGET:= " + trg.get()

def repl_all(m):
    repl = "all: "
    if debug.get() == 1:
	repl += "debug "
    if release.get() == 1:
	repl += "release "
    if simulation.get() == 1:
	repl += "simulation "
    if docs.get() == 1:
	repl += "docs "
    return repl

def repl_cflag(m):
    repl = "CCFLAGS:= -Werror -msoft-float -c -MD -mv8 -O0 -g "
    if leon3_level.get() == 1:
	repl += "-DLEON3 "
    if test_system_level.get() == 1:
	repl += "-D_TEST_SYSTEM_ "
    if error_level.get() == 1:
	repl += "-D_ERROR "
    if trace_level.get() == 1:
	repl += "-D_TRACE "
    if warn_level.get() == 1:
	repl += "-D_WARN "
    if debug_level.get() == 1:
	repl += "-D_DEBUG "
    return repl

def build_makefile():
    """generate makefile"""

    with open('makefile', 'r+') as mk:
	content = mk.read()
    mk.close()
    content = re.sub('CPU_ARCH:= (\w+)', repl_arch, content)
    content = re.sub('CC_PACKET:= (\w+(-\w+)?)', repl_compil, content)
    content = re.sub('TARGET:= (\w+)', repl_target, content)
    content = re.sub('CCFLAGS:= ([A-Za-z0-9_\-# ]+)', repl_cflag, content)
    with open('makefile', 'w+') as mk:
	mk.write(content)
    mk.close()

    with open('src/makefile', 'r+') as mk:
	content = mk.read()
    content = re.sub('all: ([a-z ]+)', repl_all, content)
    mk.close()
    with open('src/makefile', 'w+') as mk:
        mk.write(content)
    mk.close()

def About():
    view_window = Tkinter.Toplevel(root)
    about_text = "Monitor configurator"
    Tkinter.Message(view_window,
                    text=about_text,
                    justify=Tkinter.CENTER,
                    anchor=Tkinter.CENTER,
                    relief=Tkinter.GROOVE,
                    width=250).pack(padx=10, pady=10)

def file_menu():
    file_btn = Tkinter.Menubutton(menu_frame, text='File', underline=0)
    file_btn.pack(side=Tkinter.LEFT, padx="2m")
    file_btn.menu = Tkinter.Menu(file_btn)
    file_btn.menu.add_command(label="Save", underline=0, command=make_conf)
    file_btn.menu.add('separator')
    file_btn.menu.add_command(label='Exit', underline=0, command=file_btn.quit)
    file_btn['menu'] = file_btn.menu
    return file_btn

def help_menu():
    help_btn = Tkinter.Menubutton(menu_frame, text='Help', underline=0,)
    help_btn.pack(side=Tkinter.LEFT, padx="2m")
    help_btn.menu = Tkinter.Menu(help_btn)
    help_btn.menu.add_command(label="About", underline=0, command=About)
    help_btn['menu'] = help_btn.menu
    return help_btn

def main():
    global root, info_line, menu_frame
    root = Tkinter.Tk()
    root.title('Monitor configure')

    #-- Create the menu frame, and add menus to the menu frame
    menu_frame = Tkinter.Frame(root)
    menu_frame.pack(fill=Tkinter.X, side=Tkinter.TOP)
    menu_frame.tk_menuBar(file_menu(), help_menu())

    #-- Create the info frame and fill with initial contents
    info_frame = Tkinter.Frame(root)
    info_frame.pack(fill=Tkinter.X, side=Tkinter.BOTTOM, pady=1)

    #-- config tests frame
    config = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    config.pack(side=Tkinter.LEFT, padx=2, pady=1)
    Label(config, text="Test", width=15, background="lightblue").grid(row=0, column=0)
    Label(config, text="Description", width=35, background="lightblue").grid(row=0, column=1)
    var = IntVar()
    row = 1
    for test, pack, inc, status, desc in packages:
	setattr(var, test, IntVar())
	Checkbutton(config, text=test, state=status, anchor=W,
	    variable = getattr(var, test), command=(lambda row=row: onPress(row-1))).grid(row=row, column=0, sticky=W)
	getattr(var, test).set(inc)
	Label(config, text=desc, state=status, width=35, anchor=W).grid(row=row, column=1, sticky=W)
	row = row + 1


    #-- arch frame
    global arc_v
    arc_v = IntVar()
    arc = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    arc.pack(side=Tkinter.TOP, padx=3, pady=2)
    Label(arc, text="Arch", width=15, background="lightblue").grid(row=0, column=0)
    for ar, value in arch:
	Radiobutton(arc, text=ar, value=value, variable=arc_v, anchor=W).grid(row=value+1, column=0, sticky=W)
    arc_v.set(0)

    #-- compiler frame
    global cmpl
    compil = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    compil.pack(side=Tkinter.TOP, padx=3, pady=2)
    Label(compil, text="Compiler", width=15, background="lightblue").grid(row=0, column=0)
    cmpl = StringVar()
    Entry(compil, width=15, textvariable=cmpl).grid(row=1, column=0)
    cmpl.set("sparc-elf")

    #-- Target
    global trg
    targ = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    targ.pack(side=Tkinter.TOP, padx=3, pady=2)
    Label(targ, text="Target", width=15, background="lightblue").grid(row=0, column=0)
    trg = StringVar()
    Entry(targ, width=15, textvariable=trg).grid(row=1, column=0)
    trg.set("monitor")

    #-- level frame
    global error_level, trace_level, warn_level, debug_level, test_system_level, leon3_level
    level = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    level.pack(side=Tkinter.TOP, padx=3, pady=2)
    Label(level, text="Verbous level", width=15, background="lightblue").grid(row=0, column=0)
    error_level, trace_level, warn_level, debug_level, test_system_level, leon3_level = (IntVar(), IntVar(), IntVar(), IntVar(), IntVar(), IntVar())
    Checkbutton(level, text="Error", state=NORMAL, anchor=W, variable = error_level).grid(row=1, column=0, sticky=W)
    error_level.set(1)
    Checkbutton(level, text="Trace", state=NORMAL, anchor=W, variable = trace_level).grid(row=2, column=0, sticky=W)
    trace_level.set(1)
    Checkbutton(level, text="Warn", state=NORMAL, anchor=W, variable = warn_level).grid(row=3, column=0, sticky=W)
    Checkbutton(level, text="Debug", state=NORMAL, anchor=W, variable = debug_level).grid(row=4, column=0, sticky=W)
    Checkbutton(level, text="Test system", state=NORMAL, anchor=W, variable = test_system_level).grid(row=5, column=0, sticky=W)
    test_system_level.set(1)
    Checkbutton(level, text="Leon3", state=NORMAL, anchor=W, variable = leon3_level).grid(row=6, column=0, sticky=W)
    leon3_level.set(1)

    #-- build
    global debug, release, simulation, docs
    build = Tkinter.Frame(info_frame, relief=Tkinter.RAISED, borderwidth=2)
    build.pack(side=Tkinter.TOP, padx=3, pady=2)
    Label(build, text="Build", width=15, background="lightblue").grid(row=0, column=0)
    debug, release, simulation, docs = (IntVar(), IntVar(), IntVar(), IntVar())
    Checkbutton(build, text="Debug", state=NORMAL, anchor=W, variable = debug).grid(row=1, column=0, sticky=W)
    debug.set(1)
    Checkbutton(build, text="Release", state=NORMAL, anchor=W, variable = release).grid(row=2, column=0, sticky=W)
    release.set(1)
    Checkbutton(build, text="Simulation", state=NORMAL, anchor=W, variable = simulation).grid(row=3, column=0, sticky=W)
    Checkbutton(build, text="Doxygen", state=NORMAL, anchor=W, variable = docs).grid(row=4, column=0, sticky=W)

    root.mainloop()

if __name__=='__main__':
    try:
        main()
    except:
        traceback.print_exc()
