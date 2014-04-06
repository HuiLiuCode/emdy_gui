# ----------------------------------------------------------------------
# Copyright (c) 2011-2014, Hui Liu
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------

import os
import sys
from cStringIO import StringIO
from Tkinter import *
import tkMessageBox
import tkFileDialog
from math import fsum

import Pmw
from pymol import cmd, util
from pymol.cgo import *

try:
    from emdy.io import *
    from emdy.io.charmmtopfile import CharmmTopFile
    from emdy.io.charmmprmfile import CharmmPrmFile
    from emdy.setup.build import CharmmTopBuilder, CharmmCoordBuilder
    from emdy.setup.solvate import Solvater
    from emdy.setup.ionize import Ionizer
except ImportError:
    _HAS_LIB = 0
else:
    _HAS_LIB = 1

__program__ = 'EMDY GUI'
__version__ = '1.0'
__author__ = 'Hui Liu'
__email__ = 'teffliu@hotmail.com'
__url__ = 'https://github.com/emdy/emdy_gui/'
__desc__ = 'a tool for setting up molecular dynamics simulations'
__doc__ = """
The PyMOL plugin helps to setup EMDY runs and provides visual support.

Do your job as follows,

1) Make sure that the EMDY package is installed correctly.
2) Launch the plugin.
3) Set up the configuration.
4) Click the "Execute" button and wait.
5) Click the "Output" button to generate the files.

URL: %s
Author: %s <%s>
""" % (__url__, __author__, __email__)

_CUBOID = 1
_OCT = 2
_HEXP = 3
_RHDO = 4
_TRICLINIC = 5
_SPHERE = 6

IONS = {
    'Na+': 'SOD',
    'K+': 'POT',
    'Mg2+': 'MG',
    'Ca2+': 'CAL',
    'Zn2+': 'ZN2',
    'Cl-': 'CLA'
    }


def __init__(self):
    """Register function for the plugin."""
    self.menuBar.addmenuitem('Plugin', 'command',
                             '%s %s'%(__program__, __version__),
                             label='%s %s'%(__program__, __version__),
                             command=lambda x=self: EmdyGui(x))


class CleanableEntryField(Pmw.EntryField):
    def __init__(self, *args, **kwargs):
        Pmw.EntryField.__init__(self, *args, **kwargs)
        self.component('entry').bind('<Escape>',
                                     func=lambda x: self.setvalue(''))


class StdoutRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, content):
        self.widget.configure(state='normal')
        self.widget.insert('end', content)
        self.widget.configure(state='disabled')
        self.widget.see('end')

    def flush(self):
        pass


class EmdyGui:
    """EMDY GUI plugin."""

    def __init__(self, app):
        self.parent = app.root
        self.mod = None
        self.top = None
        self.prm = None
        self.pmobj = []
        self.original_stdout = sys.stdout
        self.create_widgets()
        cmd.hide('everything', 'all')

    def __del__(self):
        sys.stdout = self.original_stdout

    def create_widgets(self):
        # dialog window
        # ----------
        self.create_dialog()

        # title label
        # ----------
        self.create_title()

        # paned window
        # ----------
        self.create_panedwindow()

        # multiple pages
        # ----------
        self.create_notebook()

        # console
        # ----------
        self.create_console()

        self.show_dialog()

    def create_dialog(self):
        self.dialog = Pmw.Dialog(self.parent,
                                 buttons=('Execute', 'Output', 'Console',
                                          'Quit', 'About'),
                                 title='%s %s'%(__program__, __version__),
                                 command=self.on_dialog_button_clicked)
        w = self.dialog.component('buttonbox')
        for i in range(w.numbuttons()):
            w.button(i).configure(width=10)
        w.setdefault(0)
        self.dialog.withdraw()
        Pmw.setbusycursorattributes(self.dialog.component('hull'))

    def create_title(self):
        w = Frame(self.dialog.interior(), relief='raised', borderwidth=3)
        w.pack(fill='both', expand=0, padx=10, pady=4)
        Label(w,
              text='%s %s\n%s'%(__program__, __version__, __desc__),
              font=Pmw.logicalfont('Helvetica', 0, weight='bold'),
              bg='RoyalBlue4',
              fg='white'
              ).pack(fill='both', expand=0, ipadx=4, ipady=4)

    def create_panedwindow(self):
        self.panedwin = PanedWindow(self.dialog.interior(),
                                    orient='vertical', sashrelief='sunken')
        self.panedwin.pack(fill='both', expand=1)

    def create_console(self):
        self.console_frame = Frame(self.panedwin)
        self.console = Text(self.console_frame,
              height=10,
              width=80,
              bg='#272822',
              fg='#A6E22E',
              relief='sunken')
        sbar = Scrollbar(self.console_frame, orient='vertical',
                         command=self.console.yview)
        self.console.config(yscrollcommand=sbar.set)
        self.console.pack(side='left', fill='both', expand=1)
        sbar.pack(side='right', fill='y')
        sys.stdout = StdoutRedirector(self.console)
        self.console_shown = 0

    def create_notebook(self):
        self.notebook = Pmw.NoteBook(self.panedwin)
        self.panedwin.add(self.notebook)
        self.panedwin.paneconfigure(self.notebook, padx=10, pady=10)

        # "I/O" page
        # ==========
        self.create_io_page()

        # "Preparation" page
        # ==========
        self.create_prep_page()

        # "Solvation" page
        # ==========
        self.create_sol_page()

        # "Ionization" page
        # ==========
        self.create_ion_page()

        # make tab sizes the same
        for w in self.notebook._pageAttrs.values():
            w['tabreqwidth'] = 80

        self.notebook.setnaturalsize()

    def create_io_page(self):
        page = self.notebook.add('I/O')
        self.notebook.tab(0).focus_set()

        grp_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        frm_opt = {'fill': 'both', 'expand': 1}
        ent_opt = {'side': 'left', 'fill': 'both',
                   'expand': 1, 'padx': 10, 'pady': 5}
        btn_opt = {'side': 'right', 'fill': 'x',
                   'expand': 0, 'padx': 10, 'pady': 5}

        # "Input" group
        # **********
        group = Pmw.Group(page, tag_text='Input Files')
        group.pack(**grp_opt)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.pdbloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='PDB File:',
                command=self.on_pdbentry_pressed)

        self.openpdbbtn = Button(
                frame,
                command=self.on_openpdb_clicked,
                text='Browse',
                width=10)

        self.downloadbtn = Button(
                frame,
                command=self.on_download_clicked,
                text='Download',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.ffloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Forcefield File:')

        self.openffbtn = Button(
                frame,
                command=self.on_openff_clicked,
                text='Browse',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.parloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Parameter File:')

        self.openparbtn = Button(
                frame,
                command=self.on_openpar_clicked,
                text='Browse',
                width=10)

        # "Output" group
        # **********
        group = Pmw.Group(page, tag_text='Output Files')
        group.pack(**grp_opt)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.toploc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Topology File:')

        self.savetopbtn = Button(
                frame,
                command=self.on_savetop_clicked,
                text='SaveAs',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.crdloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Coordinate File:')

        self.savecrdbtn = Button(
                frame,
                command=self.on_savecrd_clicked,
                text='SaveAs',
                width=10)

        entries = [self.pdbloc, self.ffloc, self.parloc,
                   self.toploc, self.crdloc]
        buttons = [self.openpdbbtn, self.openffbtn, self.openparbtn,
                   self.savetopbtn, self.savecrdbtn]
        for e, b in zip(entries, buttons):
            e.pack(**ent_opt)
            b.pack(**btn_opt)
        self.downloadbtn.pack(**btn_opt)
        Pmw.alignlabels(entries)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        self.topfmt = Pmw.OptionMenu(
                frame,
                labelpos='w',
                label_text='Topology Format:',
                items=('AMBER prmtop', 'CHAMBER prmtop',
                       'GROMACS top', 'NAMD psf'),
                menubutton_width=14)
        self.topfmt.pack(side='left', anchor='w', padx=10, pady=5)

        self.crdfmt = Pmw.OptionMenu(
                frame,
                labelpos='w',
                label_text='Coordinate Format:',
                items=('AMBER inpcrd', 'GROMACS g96',
                       'GROMACS gro', 'NAMD bin', 'pdb'),
                menubutton_width=14)
        self.crdfmt.pack(side='right', anchor='w', padx=10, pady=5)

    def create_prep_page(self):
        page = self.notebook.add('Preparation')

        self.use_defrule = IntVar()
        self.use_userrule = IntVar()
        self.ign_h = IntVar()
        self.ign_lig = IntVar()
        self.ign_wat = IntVar()
        self.ign_ion = IntVar()
        self.autodisu = IntVar()
        self.userdisu = IntVar()

        self.use_defrule.set(1)
        self.use_userrule.set(0)
        self.ign_h.set(1)
        self.ign_lig.set(0)
        self.ign_wat.set(0)
        self.ign_ion.set(0)
        self.autodisu.set(0)
        self.userdisu.set(0)

        grp_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        frm_opt = {'fill': 'both', 'expand': 1}
        chk_opt = {'side': 'left', 'fill': 'x', 'expand': 0}
        btn_opt = {'side': 'left', 'fill': 'x',
                   'expand': 0, 'padx': 10, 'pady': 5}

        # "Rename"
        # **********
        group = Pmw.Group(page, tag_text='Rename')
        group.pack(**grp_opt)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        Checkbutton(frame, text='Use default rules',
                    variable=self.use_defrule).pack(**chk_opt)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        Checkbutton(frame, text='Specify a rule file:',
                    variable=self.use_userrule,
                    command=self.toggle_renloc_entry).pack(**chk_opt)
        self.renloc = CleanableEntryField(frame, entry_state='disabled')
        self.renloc.pack(side='left', fill='x', expand=1, padx=0, pady=5)
        self.openrenbtn = Button(
                frame,
                command=self.on_openren_clicked,
                text='Browse',
                width=10,
                state='disabled')
        self.openrenbtn.pack(**btn_opt)

        # "Ignore"
        # **********
        group = Pmw.Group(page, tag_text='Ignore')
        group.pack(**grp_opt)

        kw = [('hydrogens', self.ign_h), ('ligands', self.ign_lig),
              ('water', self.ign_wat), ('ions', self.ign_ion)]
        chk_opt['expand'] = 1
        for i, k in enumerate(kw):
            t, v = k
            Checkbutton(group.interior(), text=t, variable=v).pack(**chk_opt)

        # "Disulfide Bond"
        # **********
        group = Pmw.Group(page, tag_text='Disulfide Bond')
        group.pack(**grp_opt)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        chk_opt['expand'] = 0
        Checkbutton(frame, text='Automatically detect with a cutoff of',
                    variable=self.autodisu,
                    command=self.toggle_disucut_entry).pack(**chk_opt)

        self.disucut = CleanableEntryField(
                frame,
                labelpos='e',
                validate={'validator': 'real', 'min': 0.1},
                value=3.0,
                label_text=u'\xc5',
                entry_state='disabled')
        self.disucut.pack(side='left', anchor='w', padx=0, pady=5)

        frame = Frame(group.interior())
        frame.pack(**frm_opt)

        Checkbutton(frame, text='Specify a bond file:',
                    variable=self.userdisu,
                    command=self.toggle_disuloc_entry).pack(**chk_opt)
        self.disuloc = CleanableEntryField(frame, entry_state='disabled')
        self.disuloc.pack(side='left', fill='x', expand=1, padx=0, pady=5)
        self.opendisubtn = Button(
                frame,
                command=self.on_opendisu_clicked,
                text='Browse',
                width=10,
                state='disabled')
        self.opendisubtn.pack(**btn_opt)

    def toggle_state(self, w):
        if w['state'] == 'normal':
            w.configure(state='disabled')
        else:
            w.configure(state='normal')
        w.update()

    def toggle_renloc_entry(self):
        self.renloc.setvalue('')
        self.toggle_state(self.renloc.component('entry'))
        self.toggle_state(self.openrenbtn)

    def toggle_disucut_entry(self):
        self.disucut.setvalue(3.0)
        self.toggle_state(self.disucut.component('entry'))

    def toggle_disuloc_entry(self):
        self.disuloc.setvalue('')
        self.toggle_state(self.disuloc.component('entry'))
        self.toggle_state(self.opendisubtn)

    def create_sol_page(self):
        page = self.notebook.add('Solvation')

        grp_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        frm_opt = {'fill': 'both', 'expand': 1}

        frame = Frame(page)
        frame.pack(side='left', **frm_opt)

        # "Solvents"
        # **********
        igroup = Pmw.Group(frame, tag_text='Solvents')
        igroup.pack(**grp_opt)

        self.watmod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Solvent Model:',
                items=('TIP3P', 'TIP3P-CHARMM', 'TIP4P', 'TIP5P', 'SPC/E'),
                menubutton_width=12)
        self.watmod.pack(anchor='w', expand=1, padx=10, pady=5)

        self.watseg = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'alphanumeric'},
                value='WAT',
                label_text='Segment Name:')
        self.watseg.pack(anchor='w', expand=1, padx=10, pady=5)

        Pmw.alignlabels([self.watmod, self.watseg])

        # "Box Shape"
        # **********
        igroup = Pmw.Group(frame, tag_text='Box Shape')
        igroup.pack(**grp_opt)

        self.boxshape = IntVar()
        self.boxshape.set(1)
        shapes = [('cuboid', 1),
                  ('truncated octahedron', 2),
                  ('hexagonal prism', 3),
                  ('rhombic dodecahedron', 4),
                  ('general triclinic', 5),
                  ('sphere', 6)]
        for txt, val in shapes:
            Radiobutton(igroup.interior(),
                        text=txt,
                        padx=20,
                        command=self.toggle_boxpar,
                        variable=self.boxshape,
                        value=val).pack(anchor='w', expand=1)

        # "Box Parameters"
        # **********
        igroup = Pmw.Group(page, tag_text='Box Parameters')
        igroup.pack(side='right', fill='both', expand=0, padx=10, pady=5)

        w = Frame(igroup.interior())
        w.pack(fill='none', expand=0, pady=5)

        boxcen = Pmw.Group(w, tag_text=u'Center (\xc5)')
        boxcen.grid(row=0, column=0)

        self.cenx = CleanableEntryField(
                boxcen.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real'},
                value=0.0,
                label_text='x:')
        self.cenx.grid(row=0, column=0)

        self.ceny = CleanableEntryField(
                boxcen.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real'},
                value=0.0,
                label_text='y:')
        self.ceny.grid(row=1, column=0)

        self.cenz = CleanableEntryField(
                boxcen.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real'},
                value=0.0,
                label_text='z:')
        self.cenz.grid(row=2, column=0)

        boxlen = Pmw.Group(w, tag_text=u'Lengths (\xc5)')
        boxlen.grid(row=0, column=1)

        self.boxx = CleanableEntryField(
                boxlen.interior(),
                labelpos='w',
                entry_width=10,
                entry_state='disabled',
                validate={'validator': 'real', 'min': 0.1},
                label_text='a:')
        self.boxx.grid(row=0, column=0)

        self.boxy = CleanableEntryField(
                boxlen.interior(),
                labelpos='w',
                entry_width=10,
                entry_state='disabled',
                validate={'validator': 'real', 'min': 0.1},
                label_text='b:')
        self.boxy.grid(row=1, column=0)

        self.boxz = CleanableEntryField(
                boxlen.interior(),
                labelpos='w',
                entry_width=10,
                entry_state='disabled',
                validate={'validator': 'real', 'min': 0.1},
                label_text='c:')
        self.boxz.grid(row=2, column=0)

        boxang = Pmw.Group(w, tag_text=u'Angles (\xb0)')
        boxang.grid(row=0, column=2)

        self.boxa = CleanableEntryField(
                boxang.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real', 'min': 0.1},
                value=90.0,
                entry_state='disabled',
                entry_disabledforeground='black',
                label_text=u"\u03B1:")
        self.boxa.grid(row=0, column=0)

        self.boxb = CleanableEntryField(
                boxang.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real', 'min': 0.1},
                value=90.0,
                entry_state='disabled',
                entry_disabledforeground='black',
                label_text=u"\u03B2:")
        self.boxb.grid(row=1, column=0)

        self.boxc = CleanableEntryField(
                boxang.interior(),
                labelpos='w',
                entry_width=10,
                validate={'validator': 'real', 'min': 0.1},
                value=90.0,
                entry_state='disabled',
                entry_disabledforeground='black',
                label_text=u"\u03B3:")
        self.boxc.grid(row=2, column=0)

        self.use_pad = IntVar()
        self.use_pad.set(1)

        w = Frame(igroup.interior())
        w.pack()

        self.padchkbtn = Checkbutton(w, text='Use a padding of',
                    variable=self.use_pad, command=self.on_pad_chosen)
        self.padchkbtn.pack(side='left', fill='both', expand=0, pady=5)

        self.pad = CleanableEntryField(
                w,
                labelpos='e',
                validate={'validator': 'real', 'min': 0.0},
                value=10.0,
                label_text=u'\xc5',
                entry_state='normal')
        self.pad.pack(side='left', anchor='w', pady=5)

        self.cut = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                value=2.4,
                label_text=u'Overlap Cutoff (\xc5):')
        self.cut.pack(anchor='w', padx=10, pady=5)

        self.do_minsol = IntVar()
        self.do_minsol.set(0)

        Checkbutton(igroup.interior(),
                    text='rotate and minimize the number of solvents',
                    variable=self.do_minsol
                    ).pack(fill='both', expand=0, padx=10, pady=5)

        self.showaxesbtn = Button(
                igroup.interior(),
                command=self.on_showaxes_clicked,
                text='Show the axes')
        self.showaxesbtn.pack(fill='both', expand=0, padx=10, pady=5)

        self.showboxbtn = Button(
                igroup.interior(),
                command=self.on_showbox_clicked,
                text='Show the box/sphere')
        self.showboxbtn.pack(fill='both', expand=0, padx=10, pady=5)

    def toggle_boxpar(self):
        boxshape = self.boxshape.get()

        if boxshape == _CUBOID:
            for w in self.boxx, self.boxy, self.boxz:
                if w['entry_state'] == 'disabled' and not self.use_pad.get():
                    w['entry_state'] = 'normal'
                    w.setvalue('')
            for w in self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'normal':
                    w['entry_state'] = 'disabled'
                w.setvalue(90.0)
            if self.padchkbtn['state'] == 'disabled':
                self.padchkbtn['state'] = 'normal'
            if self.pad['label_state'] == 'disabled':
                self.pad['label_state'] = 'normal'

        elif boxshape == _OCT:
            for w in self.boxx, self.boxy, self.boxz:
                if w['entry_state'] == 'disabled' and not self.use_pad.get():
                    w['entry_state'] = 'normal'
                    w.setvalue('')
            for w in self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'normal':
                    w['entry_state'] = 'disabled'
                w.setvalue(109.4712190)
            if self.padchkbtn['state'] == 'disabled':
                self.padchkbtn['state'] = 'normal'
            if self.pad['label_state'] == 'disabled':
                self.pad['label_state'] = 'normal'

        elif boxshape == _HEXP:
            for w in self.boxx, self.boxy, self.boxz:
                if w['entry_state'] == 'disabled' and not self.use_pad.get():
                    w['entry_state'] = 'normal'
                    w.setvalue('')
            for w in self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'normal':
                    w['entry_state'] = 'disabled'
            self.boxa.setvalue(60.0)
            self.boxb.setvalue(90.0)
            self.boxc.setvalue(90.0)
            if self.padchkbtn['state'] == 'disabled':
                self.padchkbtn['state'] = 'normal'
            if self.pad['label_state'] == 'disabled':
                self.pad['label_state'] = 'normal'

        elif boxshape == _RHDO:
            for w in self.boxx, self.boxy, self.boxz:
                if w['entry_state'] == 'disabled' and not self.use_pad.get():
                    w['entry_state'] = 'normal'
                    w.setvalue('')
            for w in self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'normal':
                    w['entry_state'] = 'disabled'
            self.boxa.setvalue(60.0)
            self.boxb.setvalue(60.0)
            self.boxc.setvalue(90.0)
            if self.padchkbtn['state'] == 'disabled':
                self.padchkbtn['state'] = 'normal'
            if self.pad['label_state'] == 'disabled':
                self.pad['label_state'] = 'normal'

        elif boxshape == _TRICLINIC:
            for w in self.boxx, self.boxy, self.boxz:
                if w['entry_state'] == 'disabled':
                    w['entry_state'] = 'normal'
                    w.setvalue('')
            for w in self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'disabled':
                    w['entry_state'] = 'normal'
                w.setvalue('')
            self.use_pad.set(0)
            self.padchkbtn['state'] = 'disabled'
            self.pad['entry_state'] = 'disabled'
            self.pad['label_state'] = 'disabled'

        else:
            for w in self.boxx, self.boxy, self.boxz, \
                     self.boxa, self.boxb, self.boxc:
                if w['entry_state'] == 'normal':
                    w['entry_state'] = 'disabled'
                w.setvalue('')
            if self.padchkbtn['state'] == 'disabled':
                self.padchkbtn['state'] = 'normal'
            if self.pad['label_state'] == 'disabled':
                self.pad['label_state'] = 'normal'

    def on_pad_chosen(self):
        if self.pad['entry_state'] == 'disabled':
            self.pad['entry_state'] = 'normal'
            if self.boxshape.get() != _SPHERE:
                for w in self.boxx, self.boxy, self.boxz:
                    if w['entry_state'] == 'normal':
                        w['entry_state'] = 'disabled'
        else:
            self.pad['entry_state'] = 'disabled'
            if self.boxshape.get() != _SPHERE:
                for w in self.boxx, self.boxy, self.boxz:
                    if w['entry_state'] == 'disabled':
                        w['entry_state'] = 'normal'

    def create_ion_page(self):
        page = self.notebook.add('Ionization')

        frm_opt = {'fill': 'both', 'expand': 1}
        ent_opt = {'anchor': 'w', 'padx': 10, 'pady': 5,
                   'fill': 'both', 'expand': 1}

        # "Ions"
        # **********
        igroup = Pmw.Group(page, tag_text='Ions')
        igroup.pack(side='left', fill='both', expand=1, padx=10, pady=5)

        self.catmod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Cation Model:',
                menubutton_width=4,
                items=('Na+', 'K+', 'Mg2+', 'Ca2+', 'Zn2+'))
        self.catmod.pack(**ent_opt)

        self.catnum = Pmw.Counter(
                igroup.interior(),
                labelpos='w',
                label_text='Cation Number:',
                entry_width=4,
                entryfield_value=0,
                entry_state='disabled',
                datatype = {'counter': 'integer'},
                entryfield_validate={'validator': 'integer', 'min': '0'})
        self.catnum.pack(**ent_opt)

        self.animod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Anion Model:',
                menubutton_width=4,
                items=('Cl-', ))
        self.animod.pack(**ent_opt)

        self.aninum = Pmw.Counter(
                igroup.interior(),
                labelpos='w',
                label_text='Anion Number:',
                entry_width=4,
                entryfield_value=0,
                entry_state='disabled',
                datatype = {'counter': 'integer'},
                entryfield_validate={'validator': 'integer', 'min': '0'})
        self.aninum.pack(**ent_opt)

        self.ionseg = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                label_text='Segment Name:',
                entry_width=10,
                value='ION',
                validate={'validator': 'alphanumeric'})
        self.ionseg.pack(**ent_opt)

        self.do_neutral = IntVar()
        self.do_neutral.set(1)

        self.calcqbtn = Button(
                igroup.interior(),
                command=self.on_calcq_clicked,
                text='Calculate the total charge')
        self.calcqbtn.pack(fill='both', expand=0, padx=10, pady=5)

        Checkbutton(igroup.interior(),
                    text='automatically neutralize',
                    variable=self.do_neutral,
                    command=self.toggle_nions_salcon
                    ).pack(fill='both', expand=1, padx=10, pady=5)

        Pmw.alignlabels([self.catmod, self.catnum, self.animod, self.aninum,
                         self.ionseg])

        frame = Frame(page)
        frame.pack(side='right', **frm_opt)

        # "Methods"
        # **********
        igroup = Pmw.Group(frame, tag_text='Choose a method to place the ions')
        igroup.pack(fill='both', expand=1, padx=10, pady=5)

        self.ionmeth = IntVar()
        self.ionmeth.set(1)
        meths = [('randomly', 1),
                 ('by electrostatic potential', 2),
                 ('manually', 3)]
        for txt, val in meths:
            Radiobutton(igroup.interior(),
                        text=txt,
                        padx=20,
                        variable=self.ionmeth,
                        value=val).pack(anchor='w', fill='y', expand=1)#pack(anchor='w')

        # "Parameters"
        # **********
        igroup = Pmw.Group(frame, tag_text='Parameters')
        igroup.pack(fill='both', expand=1, padx=10, pady=5)

        self.ionion = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                entry_width=5,
                validate={'validator': 'real', 'min': 0.1},
                value=5.0,
                label_text=u'Ion-to-Ion Cutoff (\xc5):')
        self.ionion.pack(**ent_opt)

        self.ionsol = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                entry_width=5,
                validate={'validator': 'real', 'min': 0.1},
                value=5.0,
                label_text=u'Ion-to-Solvent Cutoff (\xc5):')
        self.ionsol.pack(**ent_opt)

        self.salcon = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                entry_width=5,
                validate={'validator': 'real', 'min': 0.0},
                value=0.0,
                label_text='Salt Concentration (mol/L):')
        self.salcon.pack(**ent_opt)

        Pmw.alignlabels([self.ionion, self.ionsol, self.salcon])

    def on_calcq_clicked(self):
        if not _HAS_LIB or self.mod is None:
            return
        q = fsum([atom.charge for atom in self.mod.atoms])
        tkMessageBox.showinfo('INFO', 'Total charge is %+f e'%q,
                              parent=self.parent)

    def toggle_nions_salcon(self):
        for w in self.catnum, self.aninum, self.salcon:
            self.toggle_state(w.component('entry'))

    def on_dialog_button_clicked(self, result):
        if result == 'Execute':
            self.on_execute_button_clicked()
        elif result == 'Output':
            self.on_output_button_clicked()
        elif result == 'Console':
            self.on_console_button_clicked()
        elif result == 'About':
            self.on_about_button_clicked()
        else:
            self.on_quit_button_clicked()

    def load_input(self):
        # check
        if not _HAS_LIB:
            tkMessageBox.showerror(
                'ERROR',
                'Please install EMDY before launch the plugin',
                parent=self.parent)
            return 1

        if not self.pdbloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a pdb file',
                                   parent=self.parent)
            return 1

        if not self.ffloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a forcefield file',
                                   parent=self.parent)
            return 1

        if not self.parloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a parameter file',
                                   parent=self.parent)
            return 1

        self.mod = PdbFile(self.pdbloc.getvalue()).read()
        self.top = CharmmTopFile(self.ffloc.getvalue()).read()
        self.prm = CharmmPrmFile(self.parloc.getvalue()).read()
        return 0

    def on_execute_button_clicked(self):
        if not _HAS_LIB:
            tkMessageBox.showerror(
                'ERROR',
                'Please install EMDY before launch the plugin',
                parent=self.parent)
            return

        if self.notebook.getcurselection() == 'Preparation':
            if self.mod is None or self.top is None or self.prm is None:
                failed = self.load_input()
                if failed:
                    return
            try:
                self.mod = add_atoms(self.mod, self.top, self.prm)
            except Exception:
                tkMessageBox.showerror(
                    'ERROR',
                    'Failed',
                    parent=self.parent)
            else:
                tkMessageBox.showinfo(
                    'INFO',
                    'Successfully completed',
                    parent=self.parent)

        elif self.notebook.getcurselection() == 'Solvation':
            if self.mod is None or self.top is None or self.prm is None:
                failed = self.load_input()
                if failed:
                    return
            try:
                self.mod = add_solvents(self.mod, self.watmod.getvalue(),
                                        self.watseg.getvalue(),
                                        self.boxshape.get(),
                                        float(self.pad.getvalue()),
                                        float(self.cut.getvalue()))
            except Exception:
                tkMessageBox.showerror(
                    'ERROR',
                    'Failed',
                    parent=self.parent)
            else:
                tkMessageBox.showinfo(
                    'INFO',
                    'Successfully completed',
                    parent=self.parent)

        elif self.notebook.getcurselection() == 'Ionization':
            if self.mod is None or self.top is None or self.prm is None:
                failed = self.load_input()
                if failed:
                    return

            if self.do_neutral.get():
                catnum = aninum = 0
            else:
                catnum = int(self.catnum.getvalue())
                aninum = int(self.aninum.getvalue())
                if catnum == aninum == 0:
                    return

            catmod = IONS[self.catmod.getvalue()]
            animod = IONS[self.animod.getvalue()]

            try:
                self.mod = add_ions(self.mod, catmod, catnum, animod, aninum,
                                    float(self.salcon.getvalue()),
                                    float(self.ionsol.getvalue()),
                                    float(self.ionion.getvalue()), None,
                                    self.ionseg.getvalue(), self.ionmeth.get())
            except Exception:
                tkMessageBox.showerror(
                    'ERROR',
                    'Failed',
                    parent=self.parent)
            else:
                tkMessageBox.showinfo(
                    'INFO',
                    'Successfully completed',
                    parent=self.parent)

        else:
            if self.mod is None or self.top is None or self.prm is None:
                self.load_input()
            return

        # generate a tmp file for view
        objname = {'Preparation': 'modified', 'Solvation': 'solvated',
                   'Ionization': 'ionized'}[self.notebook.getcurselection()]
        tmpfp = StringIO()
        with PdbFile(tmpfp, 'w') as f:
            f.write(self.mod)
            for obj in self.pmobj:
                cmd.delete(obj)
            cmd.read_pdbstr(tmpfp.getvalue(), objname)
            util.cbag()
            self.pmobj = [objname]
            if self.notebook.getcurselection() == 'Ionization':
                cmd.show('spheres', 'segi %s'%self.ionseg.getvalue())

    def on_output_button_clicked(self):
        # check
        if not _HAS_LIB:
            tkMessageBox.showerror(
                'ERROR',
                'Please install EMDY before launch the plugin',
                parent=self.parent)
            return

        if self.mod is None or self.top is None or self.prm is None:
            failed = self.load_input()
            if failed:
                return

        if not self.toploc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a topology file',
                                   parent=self.parent)
            return

        if not self.toploc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a coordinate file',
                                   parent=self.parent)
            return

        ffinfo = int(self.top.titles[-1].split()[0]), self.top.titles[0]
        save_files(self.mod, self.prm, self.topfmt.getvalue(),
                   self.toploc.getvalue(), self.crdfmt.getvalue(),
                   self.crdloc.getvalue(), ffinfo)
        tkMessageBox.showinfo('INFO', '2 files were generated',
                              parent=self.parent)

    def on_console_button_clicked(self):
        if self.console_shown:
            self.panedwin.forget(self.console_frame)
            self.console_shown = 0
        else:
            self.panedwin.add(self.console_frame)
            self.panedwin.paneconfigure(self.console_frame, padx=10, pady=10)
            self.console_shown = 1

    def on_about_button_clicked(self):
        about = Pmw.MessageDialog(self.parent, title='About the plugin',
                                  buttons=('Close',), defaultbutton=0,
                                  message_text=__doc__, message_justify='left')
        about.component('buttonbox').button(0).configure(width=10)
        about.activate(geometry='centerscreenfirst')

    def on_quit_button_clicked(self):
        for obj in self.pmobj:
            cmd.delete(obj)
        self.dialog.withdraw()

    def on_download_clicked(self):
        pdb = self.pdbloc.getvalue()
        try:
            PdbFile.download(pdb)
        except Exception:
            tkMessageBox.showerror('ERROR', 'Failed to download "%s"'%pdb,
                                   parent=self.parent)
        else:
            self.pdbloc.setvalue(os.path.join(os.getcwd(), pdb.upper()+'.pdb'))
            self.on_pdbentry_pressed()

    def on_pdbentry_pressed(self):
        pdb = self.pdbloc.getvalue()
        if self.check_exist(pdb) == Pmw.OK:
            cmd.load(pdb, 'original', format='pdb', quiet=0)
            util.cbag()
            self.pmobj.append('original')

    def on_openpdb_clicked(self, event=None):
        self.pdbloc.setvalue(
                tkFileDialog.askopenfilename(
                    defaultextension='.pdb .ent',
                    filetypes=[('PDB File', '.pdb .ent'),
                               ('All Files', '.*')]))
        self.on_pdbentry_pressed()

    def on_openff_clicked(self, event=None):
        self.ffloc.setvalue(
                tkFileDialog.askopenfilename(
                    defaultextension='.inp .top',
                    filetypes=[('Forcefield File', '.inp .top'),
                               ('All Files', '.*')]))

    def on_openpar_clicked(self, event=None):
        self.parloc.setvalue(
                tkFileDialog.askopenfilename(
                    defaultextension='.prm',
                    filetypes=[('Parameter File', '.prm'),
                               ('All Files', '.*')]))

    def on_savetop_clicked(self, event=None):
        tops = {'AMBER prmtop': '.prmtop',
                'CHAMBER prmtop': '.prmtop',
                'GROMACS top': '.top',
                'NAMD psf': '.psf'}
        top = tops[self.topfmt.getvalue()]
        self.toploc.setvalue(
                tkFileDialog.asksaveasfilename(
                    defaultextension=top,
                    filetypes=[('Topology File', top),
                               ('All Files', '.*')]))

    def on_savecrd_clicked(self, event=None):
        crds = {'AMBER inpcrd': '.inpcrd',
                'GROMACS g96': '.g96',
                'GROMACS gro': '.gro',
                'NAMD bin': '.bin',
                'pdb': '.pdb'}
        crd = crds[self.crdfmt.getvalue()]
        self.crdloc.setvalue(
                tkFileDialog.asksaveasfilename(
                    defaultextension=crd,
                    filetypes=[('Coordinate File', crd),
                               ('All Files', '.*')]))

    def on_openren_clicked(self, event=None):
        self.renloc.setvalue(
                tkFileDialog.askopenfilename(
                    defaultextension='.yml .yaml',
                    filetypes=[('Rename Rule File', '.yml .yaml'),
                               ('All Files', '.*')]))

    def on_opendisu_clicked(self, event=None):
        self.disuloc.setvalue(
                tkFileDialog.askopenfilename(
                    defaultextension='.yml .yaml',
                    filetypes=[('Bond File', '.yml .yaml'),
                               ('All Files', '.*')]))

    def on_showaxes_clicked(self, event=None):
        if self.showaxesbtn['text'] == 'Show the axes':
            draw_axes()
            self.showaxesbtn['text'] = 'Hide the axes'
        else:
            cmd.delete('axes')
            self.showaxesbtn['text'] = 'Show the axes'

    def on_showbox_clicked(self, event=None):
        if self.showboxbtn['text'] == 'Show the box/sphere':
            if self.boxshape.get() != _SPHERE:
                draw_box()
            else:
                draw_sphere()
            self.showboxbtn['text'] = 'Hide the box/sphere'
        else:
            if self.boxshape != 'sphere':
                cmd.delete('box')
            else:
                cmd.delete('sphere')
            self.showboxbtn['text'] = 'Show the box/sphere'

    def check_exist(self, s):
        if not s:
            return Pmw.PARTIAL
        elif os.path.isfile(s):
            return Pmw.OK
        elif os.path.exists(s):
            return Pmw.PARTIAL
        else:
            return Pmw.PARTIAL

    def show_dialog(self):
        self.dialog.show()


if _HAS_LIB:

    def add_atoms(mod, top, prm):
        builder = CharmmTopBuilder(mod, top)
        mod = builder.build()
        cbuilder = CharmmCoordBuilder(mod, prm)
        mod = cbuilder.complete_coords()
        return mod

    def add_solvents(mod, solvent, segname, shape, pad, cut):
        solvater = Solvater(mod, solvent=solvent, segname=segname)

        if shape == _CUBOID:
            mod = solvater.as_cuboid(pad=pad, cut=cut)
        elif shape == _OCT:
            mod = solvater.as_truncated_octahedron(pad=pad, cut=cut)
        elif shape == _HEXP:
            mod = solvater.as_hexagonal_prism(pad=pad, cut=cut)
        elif shape == _RHDO:
            mod = solvater.as_rhombic_dodecahedron(pad=pad, cut=cut)
        return mod

    def add_ions(mod, cation, ncations, anion, nanions, saltcon, ionsol,
                 ionion, volume, segname, method):
        ionizer = Ionizer(mod, cation=cation, ncations=ncations, anion=anion,
                          nanions=nanions, saltcon=saltcon, ionsol=ionsol,
                          ionion=ionion, volume=volume, segname=segname)

        if method == 1:
            mod = ionizer.by_random()
        elif method == 2:
            mod = ionizer.by_potential()
        return mod

    def save_files(mod, prm, topfmt, topfile, crdfmt, crdfile, ffinfo):
        if topfmt == 'NAMD psf':
            PsfFile(topfile, 'w').write(mod)
        elif topfmt == 'AMBER prmtop':
            PrmtopFile(topfile, 'w').write(mod, prm, 1, None, chamber=False)
        elif topfmt == 'CHAMBER prmtop':
            PrmtopFile(topfile, 'w').write(mod, prm, 1, ffinfo, chamber=True)
        elif topfmt == 'GROMACS top':
            pass
        else:
            raise ValueError('Unsupported topology format' % topfmt)

        if crdfmt == 'pdb':
            PdbFile(crdfile, 'w').write(mod)
        elif crdfmt == 'NAMD bin':
            NamdBinFile(crdfile, 'w').write(mod.coords)
        elif crdfmt == 'AMBER inpcrd':
            AmberTxtRstFile(crdfile, 'w').write(mod.coords)
        elif crdfmt == 'GROMACS g96':
            G96File(crdfile, 'w').write(mod)
        elif crdfmt == 'GROMACS gro':
            GroFile(crdfile, 'w').write(mod)
        else:
            raise ValueError('Unsupported coordinate format' % crdfmt)


def draw_axes():
    pass

def draw_box():
    pass

def draw_sphere():
    pass
