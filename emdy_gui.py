# Copyright Notice
# ================
#
# The PyMOL Plugin source code in this file is copyrighted, but you can
# freely use and copy it as long as you don't change or remove any of
# the copyright notices.
#
# ----------------------------------------------------------------------
# This PyMOL Plugin is Copyright (C) 2011-2014 by Hui Liu
#
#                        All Rights Reserved
#
# Permission to use, copy, modify, distribute, and distribute modified
# versions of this software and its documentation for any purpose and
# without fee is hereby granted, provided that the above copyright
# notice appear in all copies and that both the copyright notice and
# this permission notice appear in supporting documentation, and that
# the name(s) of the author(s) not be used in advertising or publicity
# pertaining to distribution of the software without specific, written
# prior permission.
#
# THE AUTHOR(S) DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS.  IN
# NO EVENT SHALL THE AUTHOR(S) BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
# USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
# ----------------------------------------------------------------------

import os
from Tkinter import *
import tkMessageBox
import tkFileDialog

import Pmw
from pymol import cmd

try:
    from emdy.io import *
    from emdy.io.charmmtopfile import CharmmTopFile
    from emdy.io.charmmprmfile import CharmmPrmFile
    from emdy.setup.build import CharmmTopBuilder, CharmmCoordBuilder
    from emdy.setup.solvate import Solvater
    from emdy.setup.ionize import Ionizer
except ImportError:
    HAS_LIB = 0
else:
    HAS_LIB = 1

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
4) Click the "Start" button and wait.

Author: %s <%s>
Website: %s
""" % (__author__, __email__, __url__)


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


class EmdyGui:
    """EMDY GUI plugin."""

    def __init__(self, app):
        self.parent = app.root
        self.create_widgets()

    def create_widgets(self):
        # dialog window
        # ----------
        self.create_dialog()

        # title label
        # ----------
        self.create_title()

        # notebook, including multiple pages
        # ----------
        self.create_notebook()

        self.show_all()

    def create_dialog(self):
        self.dialog = Pmw.Dialog(self.parent,
                                 buttons=('Start', 'About', 'Quit'),
                                 title='%s %s'%(__program__, __version__),
                                 command=self.on_dialog_button_clicked)
        w = self.dialog.component('buttonbox')
        for i in range(w.numbuttons()):
            w.button(i).configure(width=10)
        w.setdefault(0)
        self.dialog.withdraw()
        Pmw.setbusycursorattributes(self.dialog.component('hull'))

    def create_title(self):
        Label(self.dialog.interior(),
              text='%s %s\n%s'%(__program__, __version__, __desc__),
              font=Pmw.logicalfont('Helvetica', 0, weight='bold'),
              bg='RoyalBlue4',
              fg='white'
              ).pack(fill='both', expand=0, padx=4, pady=4, ipadx=4, ipady=4)

    def create_notebook(self):
        self.notebook = Pmw.NoteBook(self.dialog.interior())
        self.notebook.pack(fill='both', expand=1, padx=10, pady=10)

        # "I/O" page
        # ==========
        self.create_io_page()

        # "Preparation" page
        # ==========
        self.create_prep_page()

        # "Solvate" page
        # ==========
        self.create_sol_page()

        # "ionize" page
        # ==========
        self.create_ion_page()

        # make tab sizes the same
        for w in self.notebook._pageAttrs.values():
            w['tabreqwidth'] = 80

        self.notebook.setnaturalsize()

    def create_io_page(self):
        page = self.notebook.add('I/O')
        self.notebook.tab(0).focus_set()

        gro_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        fra_opt = {'fill': 'both', 'expand': 1}
        ent_opt = {'side': 'left', 'fill': 'both',
                   'expand': 1, 'padx': 10, 'pady': 5}
        but_opt = {'side': 'right', 'fill': 'x',
                   'expand': 0, 'padx': 10, 'pady': 5}

        # "Input" group
        # **********
        group = Pmw.Group(page, tag_text='Input Files')
        group.pack(**gro_opt)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.pdbloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='PDB File:',
                command=self.on_pdbentry_pressed)

        self.openpdbbut = Button(
                frame,
                command=self.on_openpdb_clicked,
                text='Browse',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.ffloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Forcefield File:')

        self.openffbut = Button(
                frame,
                command=self.on_openff_clicked,
                text='Browse',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.parloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Parameter File:')

        self.openparbut = Button(
                frame,
                command=self.on_openpar_clicked,
                text='Browse',
                width=10)

        # "Output" group
        # **********
        group = Pmw.Group(page, tag_text='Output Files')
        group.pack(**gro_opt)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.toploc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Topology File:')

        self.savetopbut = Button(
                frame,
                command=self.on_savetop_clicked,
                text='SaveAs',
                width=10)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.crdloc = CleanableEntryField(
                frame,
                labelpos='w',
                label_text='Coordinate File:')

        self.savecrdbut = Button(
                frame,
                command=self.on_savecrd_clicked,
                text='SaveAs',
                width=10)

        entries = [self.pdbloc, self.ffloc, self.parloc,
                   self.toploc, self.crdloc]
        buttons = [self.openpdbbut, self.openffbut, self.openparbut,
                   self.savetopbut, self.savecrdbut]
        for e, b in zip(entries, buttons):
            e.pack(**ent_opt)
            b.pack(**but_opt)
        Pmw.alignlabels(entries)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        self.topfmt = Pmw.OptionMenu(
                frame,
                labelpos='w',
                label_text='Topology File Format:',
                items=('Amber prmtop', 'Gromacs top', 'NAMD psf'),
                menubutton_width=16)
        self.topfmt.pack(side='left', anchor='w', padx=10, pady=5)

        self.crdfmt = Pmw.OptionMenu(
                frame,
                labelpos='w',
                label_text='Coordinate File Format:',
                items=('Amber inpcrd', 'Gromacs g96',
                       'Gromacs gro', 'NAMD bin', 'pdb'),
                menubutton_width=16)
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

        gro_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        fra_opt = {'fill': 'both', 'expand': 1}
        chk_opt = {'side': 'left', 'fill': 'x', 'expand': 0}
        but_opt = {'side': 'left', 'fill': 'x',
                   'expand': 0, 'padx': 10, 'pady': 5}

        # "Rename"
        # **********
        group = Pmw.Group(page, tag_text='Rename')
        group.pack(**gro_opt)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        Checkbutton(frame, text='Use default rules',
                    variable=self.use_defrule).pack(**chk_opt)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        Checkbutton(frame, text='Specify a rule file:',
                    variable=self.use_userrule,
                    command=self.toggle_renloc_entry).pack(**chk_opt)
        self.renloc = CleanableEntryField(frame, entry_state='disabled')
        self.renloc.pack(side='left', fill='x', expand=1, padx=0, pady=5)
        self.openrenbut = Button(
                frame,
                command=self.on_openren_clicked,
                text='Browse',
                width=10,
                state='disabled')
        self.openrenbut.pack(**but_opt)

        # "Ignore"
        # **********
        group = Pmw.Group(page, tag_text='Ignore')
        group.pack(**gro_opt)

        kw = [('hydrogens', self.ign_h), ('ligands', self.ign_lig),
              ('water', self.ign_wat), ('ions', self.ign_ion)]
        chk_opt['expand'] = 1
        for i, k in enumerate(kw):
            t, v = k
            Checkbutton(group.interior(), text=t, variable=v).pack(**chk_opt)

        # "Disulfide Bond"
        # **********
        group = Pmw.Group(page, tag_text='Disulfide Bond')
        group.pack(**gro_opt)

        frame = Frame(group.interior())
        frame.pack(**fra_opt)

        chk_opt['expand'] = 0
        Checkbutton(frame, text='Auto detect with a cutoff of',
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
        frame.pack(**fra_opt)

        Checkbutton(frame, text='Specify a bond file:',
                    variable=self.userdisu,
                    command=self.toggle_disuloc_entry).pack(**chk_opt)
        self.disuloc = CleanableEntryField(frame, entry_state='disabled')
        self.disuloc.pack(side='left', fill='x', expand=1, padx=0, pady=5)
        self.opendisubut = Button(
                frame,
                command=self.on_opendisu_clicked,
                text='Browse',
                width=10,
                state='disabled')
        self.opendisubut.pack(**but_opt)

    def toggle_state(self, w):
        if w['state'] == 'normal':
            w.configure(state='disabled')
        else:
            w.configure(state='normal')
        w.update()

    def toggle_renloc_entry(self):
        self.renloc.setvalue('')
        self.toggle_state(self.renloc.component('entry'))
        self.toggle_state(self.openrenbut)

    def toggle_disucut_entry(self):
        self.disucut.setvalue(3.0)
        self.toggle_state(self.disucut.component('entry'))

    def toggle_disuloc_entry(self):
        self.disuloc.setvalue('')
        self.toggle_state(self.disuloc.component('entry'))
        self.toggle_state(self.opendisubut)

    def create_sol_page(self):
        page = self.notebook.add('Solvation')

        gro_opt = {'fill': 'both', 'expand': 1, 'padx': 10, 'pady': 5}
        fra_opt = {'fill': 'both', 'expand': 1}

        self.do_sol = IntVar()
        self.do_sol.set(0)

        # "Settings" group
        # **********
        group = Pmw.Group(page, tag_pyclass=Checkbutton,
                          tag_text='Add Solvents', tag_variable=self.do_sol)
        group.pack(**gro_opt)
        group.configure(tag_command=group.toggle)
        group.collapse()
        # hacked from Pmw source code
        group.showing = 0

        frame = Frame(group.interior())
        frame.pack(side='left', **fra_opt)

        # "Solvents"
        # ++++++++++
        igroup = Pmw.Group(frame, tag_text='Solvents')
        igroup.pack(**gro_opt)

        self.watmod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Solvent Name:',
                items=('TIP3P', 'TIP3P-CHARMM'),
                menubutton_width=12)
        self.watmod.pack(anchor='w', padx=10, pady=5)

        self.watseg = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'alphanumeric'},
                value='WAT',
                label_text='Segment Name:')
        self.watseg.pack(anchor='w', padx=10, pady=5)

        Pmw.alignlabels([self.watmod, self.watseg])

        # "Box Shape"
        # ++++++++++
        igroup = Pmw.Group(frame, tag_text='Box Shape')
        igroup.pack(**gro_opt)

        self.boxshape = IntVar()
        self.boxshape.set(1)
        shapes = [('cuboid', 1),
                  ('truncated octahedron', 2),
                  ('hexagonal prism', 3),
                  ('rhombic dodecahedron', 4),
                  ('sphere', 5)]
        for txt, val in shapes:
            Radiobutton(igroup.interior(),
                        text=txt,
                        padx=20,
                        variable=self.boxshape,
                        value=val).pack(anchor='w')

        # "Box Parameters"
        # ++++++++++
        igroup = Pmw.Group(group.interior(), tag_text='Box Parameters')
        igroup.pack(side='right', fill='both', expand=0, padx=10, pady=5)

        self.pad = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.0},
                value=10.0,
                label_text=u'Padding (\xc5):')
        self.pad.pack(anchor='w', padx=10, pady=5)

        self.cut = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                value=2.4,
                label_text=u'Overlap Cutoff (\xc5):')
        self.cut.pack(anchor='w', padx=10, pady=5)

        self.lenx = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                label_text=u'Length of Axis X (\xc5):')
        self.lenx.pack(anchor='w', padx=10, pady=5)

        self.leny = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                label_text=u'Length of Axis Y (\xc5):')
        self.leny.pack(anchor='w', padx=10, pady=5)

        self.lenz = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                label_text=u'Length of Axis Z (\xc5):')
        self.lenz.pack(anchor='w', padx=10, pady=5)

        self.do_minsol = IntVar()
        self.do_minsol.set(0)

        Checkbutton(igroup.interior(), text='minimize the number of solvents',
                    variable=self.do_minsol
                    ).pack(fill='both', expand=0, padx=10)

        self.showboxbut = Button(
                igroup.interior(),
                command=self.on_showbox_clicked,
                text='Show the box borders')
        self.showboxbut.pack(fill='x', expand=0, padx=10, pady=5)

        Pmw.alignlabels([self.pad, self.cut, self.lenx, self.leny, self.lenz])

    def create_ion_page(self):
        page = self.notebook.add('Ionization')

        fra_opt = {'fill': 'both', 'expand': 1}
        ent_opt = {'anchor': 'w', 'padx': 10, 'pady': 5,
                   'fill': 'both', 'expand': 1}

        self.do_ion = IntVar()
        self.do_ion.set(0)

        # "Settings" group
        # **********
        group = Pmw.Group(page, tag_pyclass=Checkbutton,
                          tag_text='Add Ions', tag_variable=self.do_ion)
        group.pack(fill='both', expand=1, padx=10, pady=5)
        group.configure(tag_command=group.toggle)
        group.collapse()
        # hacked from Pmw source code
        group.showing = 0

        # "Ions"
        # ++++++++++
        igroup = Pmw.Group(group.interior(), tag_text='Ions')
        igroup.pack(side='left', fill='both', expand=1, padx=10, pady=5)

        self.catmod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Cation Name:',
                #menubutton_width=4,
                items=('Na+', 'K+', 'Mg2+', 'Ca2+', 'Zn2+'))
        self.catmod.pack(**ent_opt)

        self.catnum = Pmw.Counter(
                igroup.interior(),
                labelpos='w',
                label_text='Cation Number:',
                #entry_width=4,
                entryfield_value=0,
                datatype = {'counter': 'integer'},
                entryfield_validate={'validator': 'integer', 'min': '0'})
        self.catnum.pack(**ent_opt)

        self.animod = Pmw.OptionMenu(
                igroup.interior(),
                labelpos='w',
                label_text='Anion Name:',
                #menubutton_width=4,
                items=('Cl-', ))
        self.animod.pack(**ent_opt)

        self.aninum = Pmw.Counter(
                igroup.interior(),
                labelpos='w',
                label_text='Anion Number:',
                #entry_width=4,
                entryfield_value=0,
                datatype = {'counter': 'integer'},
                entryfield_validate={'validator': 'integer', 'min': '0'})
        self.aninum.pack(**ent_opt)

        self.ionseg = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                label_text='Segment Name:',
                #entry_width=10,
                value='ION',
                validate={'validator': 'alphanumeric'})
        self.ionseg.pack(**ent_opt)

        Pmw.alignlabels([self.catmod, self.catnum, self.animod,
                         self.aninum, self.ionseg])

        frame = Frame(group.interior())
        frame.pack(side='right', **fra_opt)

        # "Methods"
        # ++++++++++
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
                        value=val).pack(anchor='w')

        # "Parameters"
        # ++++++++++
        igroup = Pmw.Group(frame, tag_text='Parameters')
        igroup.pack(fill='both', expand=1, padx=10, pady=5)

        self.salcon = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.0},
                value=0.0,
                label_text='Salt Concentration (mol/L):')
        self.salcon.pack(**ent_opt)

        self.ionion = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                value=5.0,
                label_text=u'Ion to Ion Distance (\xc5):')
        self.ionion.pack(**ent_opt)

        self.ionsol = CleanableEntryField(
                igroup.interior(),
                labelpos='w',
                validate={'validator': 'real', 'min': 0.1},
                value=5.0,
                label_text=u'Ion to Solvent Distance (\xc5):')
        self.ionsol.pack(**ent_opt)

        Pmw.alignlabels([self.salcon, self.ionion, self.ionsol])

    def on_dialog_button_clicked(self, result):
        if result == 'Start':
            self.on_start_button_clicked()
        elif result == 'About':
            self.on_about_button_clicked() 
        else:
            self.dialog.withdraw()

    def on_start_button_clicked(self):
        if not HAS_LIB:
            tkMessageBox.showerror(
                'ERROR',
                'Please install EMDY before launch the plugin',
                parent=self.parent)
            return

        # check
        if not self.pdbloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a pdb file',
                                   parent=self.parent)
            return

        if not self.ffloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a forcefield file',
                                   parent=self.parent)
            return

        if not self.parloc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a parameter file',
                                   parent=self.parent)
            return

        if not self.toploc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a topology file',
                                   parent=self.parent)
            return

        if not self.toploc.getvalue():
            tkMessageBox.showerror('ERROR', 'Please specify a coordinate file',
                                   parent=self.parent)
            return

        self.mod = PdbFile(self.pdbloc.getvalue()).read()
        self.top = CharmmTopFile(self.ffloc.getvalue()).read()
        self.prm = CharmmPrmFile(self.parloc.getvalue()).read()

        add_atoms(self.mod, self.top, self.prm)

        if self.do_sol.get():
            self.mod = add_solvents(self.mod, self.watmod.getvalue(),
                         self.watseg.getvalue(), self.boxshape.get(),
                         float(self.pad.getvalue()), float(self.cut.getvalue()))

        if self.do_ion.get():
            self.mod = add_ions(self.mod, self.catmod.getvalue(),
                     int(self.catnum.getvalue()),
                     self.animod.getvalue(), int(self.aninum.getvalue()),
                     float(self.salcon.getvalue()),
                     float(self.ionsol.getvalue()),
                     float(self.ionion.getvalue()), None,
                     self.ionseg.getvalue(), self.ionmeth.get())

        ffinfo = int(self.top.titles[-1].split()[0]), self.top.titles[0]
        save_files(self.mod, self.prm, self.topfmt.getvalue(),
                   self.toploc.getvalue(), self.crdfmt.getvalue(),
                   self.crdloc.getvalue(), ffinfo)

        # generate a tmp file for view
        PdbFile('emdy.tmp.pdb', 'w').write(self.mod)
        cmd.hide('everything', 'all')
        cmd.load('emdy.tmp.pdb', quiet=0)

    def on_about_button_clicked(self):
        about = Pmw.MessageDialog(self.parent, title='About the plugin',
                                  buttons=('Close',), defaultbutton=0,
                                  message_text=__doc__, message_justify='left')
        about.component('buttonbox').button(0).configure(width=10)
        about.activate(geometry='centerscreenfirst')

    def on_pdbentry_pressed(self):
        pdb = self.pdbloc.getvalue()
        if self.check_exist(pdb) == Pmw.OK:
            cmd.load(pdb, quiet=0)

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
        tops = {'Amber prmtop': '.prmtop',
                'Chamber prmtop': '.prmtop',
                'Gromacs top': '.top',
                'NAMD psf': '.psf'}
        top = tops[self.topfmt.getvalue()]
        self.toploc.setvalue(
                tkFileDialog.asksaveasfilename(
                    defaultextension=top,
                    filetypes=[('Topology File', top),
                               ('All Files', '.*')]))

    def on_savecrd_clicked(self, event=None):
        crds = {'Amber inpcrd': '.inpcrd',
                'Gromacs g96': '.g96',
                'Gromacs gro': '.gro',
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

    def on_showbox_clicked(self, event=None):
        pass

    def check_exist(self, s):
        if not s:
            return Pmw.PARTIAL
        elif os.path.isfile(s):
            return Pmw.OK
        elif os.path.exists(s):
            return Pmw.PARTIAL
        else:
            return Pmw.PARTIAL

    def show_all(self):
        self.dialog.show()


if HAS_LIB:

    def add_atoms(mod, top, prm):
        builder = CharmmTopBuilder(mod, top)
        mod = builder.build()
        cbuilder = CharmmCoordBuilder(mod, prm)
        mod = cbuilder.complete_coords()
        return mod

    def add_solvents(mod, solvent, segname, shape, pad, cut):
        solvater = Solvater(mod, solvent=solvent, segname=segname)

        if shape == 1:
            mod = solvater.as_cuboid(pad=pad, cut=cut)
        elif shape == 2:
            mod = solvater.as_truncated_octahedron(pad=pad, cut=cut)
        elif shape == 3:
            mod = solvater.as_hexagonal_prism(pad=pad, cut=cut)
        elif shape == 4:
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
        elif topfmt == 'Amber prmtop':
            PrmtopFile(topfile, 'w').write(mod, prm, 1, None, chamber=False)
        elif topfmt == 'Chamber prmtop':
            PrmtopFile(topfile, 'w').write(mod, prm, 1, ffinfo, chamber=True)
        elif topfmt == 'Gromacs top':
            pass
        else:
            raise ValueError('Unsupported topology format' % topfmt)

        if crdfmt == 'pdb':
            PdbFile(crdfile, 'w').write(mod)
        elif crdfmt == 'NAMD bin':
            NamdBinFile(crdfile, 'w').write(mod.coords)
        elif crdfmt == 'Amber inpcrd':
            AmberTxtRstFile(crdfile, 'w').write(mod.coords)
        elif crdfmt == 'Gromacs g96':
            G96File(crdfile, 'w').write(mod)
        elif crdfmt == 'Gromacs gro':
            GroFile(crdfile, 'w').write(mod)
        else:
            raise ValueError('Unsupported coordinate format' % crdfmt)
