import os
import logging
from numpy import *
import numpy.linalg as la

from .utilities import *
from .constants import *
from .mesh import *
from .exodusii import File
from .step_repository import step_repository
from .material import Material

__all__ = ['fe_model']

class fe_model(object):
    """The base finite element class"""
    def __init__(self, mesh=None, jobid=None):
        self.jobid = jobid or 'Job-1'
        self.dimensions = None
        self.materials = {}
        self.initial_temp = []
        self.pr_bc = []
        self.fh = None
        self.steps = None
        self._setup = False

        self._mesh = None
        if mesh is not None:
            if not isinstance(mesh, Mesh):
                raise UserInputError('mesh must be a Mesh object')
            self.mesh = mesh

    @property
    def exofile(self):
        if self.fh is not None:
            return self.fh
        self.fh = File(self.jobid+'.exo', mode='w')
        self.fh.genesis(self.mesh.nodmap, self.mesh.elemap, self.mesh.coord,
                        self.mesh.element_blocks, nodesets=self.mesh.nodesets,
                        elemsets=self.mesh.elemsets, sidesets=self.mesh.surfaces)
        return self.fh

    @property
    def mesh(self):
        return self._mesh

    @mesh.setter
    def mesh(self, mesh):

        if self._mesh is not None:
            logging.warn('MESH ALREADY ASSIGNED, OVERWRITING')

        if not isinstance(mesh, Mesh):
            raise UserInputError('MESH MUST BE A MESH OBJECT')

        self._mesh = mesh
        self.dimensions = self.mesh.dimensions
        self.numele = self.mesh.numele
        self.elements = empty(self.numele, dtype=object)
        self.numnod = self.mesh.numnod
        self._setup = False

    def genesis_mesh(self, filename):
        """
        Generates a finite element mesh from a Genesis file.

        See Also
        --------
        felab.mesh.genesis_mesh

        """
        self.mesh = genesis_mesh(filename=filename)

    def abaqus_mesh(self, filename):
        """
        Generates a finite element mesh from a Abaqus input file.

        See Also
        --------
        felab.mesh.abaqus_mesh

        """
        self.mesh = abaqus_mesh(filename=filename)

    def vtk_mesh(self, filename):
        """
        Generates a finite element mesh from a vtk .vtu file.

        See Also
        --------
        felab.mesh.vtk_mesh

        """
        self.mesh = vtk_mesh(filename=filename)

    def rectilinear_mesh(self, nx=1, ny=1, lx=1, ly=1, shift=None):
        """
        Generates a rectilinear 2D finite element mesh.

        See Also
        --------
        felab.mesh.rectilinear_mesh_2d

        """
        self.mesh = rectilinear_mesh_2d(nx=nx, ny=ny, lx=lx, ly=ly, shift=shift)

    def unit_square_mesh(self, nx=1, ny=1, shift=None):
        """
        Generates a rectilinear 2D finite element mesh.

        See Also
        --------
        felab.mesh.unit_square_mesh

        """
        self.mesh = unit_square_mesh(nx=nx, ny=ny, shift=shift)

    def create_mesh(self, **kwds):
        """
        Generates the finite element mesh.

        See Also
        --------
        felab.mesh.Mesh

        """
        self.mesh = Mesh(**kwds)

    @property
    def dofs(self):
        return self.steps.last.dofs

    @property
    def orphaned_elements(self):
        return [iel for (iel, el) in enumerate(self.elements) if el is None]

    def setup(self):

        if self._setup:
            raise RuntimeError('SETUP MUST BE PERFORMED ONLY ONCE')

        # VALIDATE USER INPUT
        if self.orphaned_elements:
            raise UserInputError('ALL ELEMENTS MUST BE ASSIGNED '
                                 'TO AN ELEMENT BLOCK')

        # CHECK VALIDITY OF ELEMENTS
        self._check_element_validity()

        # NODE FREEDOM ASSOCIATION TABLE
        active_dof = [None] * MDOF
        self.nodfat = zeros((self.numnod, MDOF), dtype=int)
        for el in self.elements:
            for (i, node) in enumerate(el.inodes):
                nfs = el.signature[i]
                nf = [max(nfs[j], self.nodfat[node,j]) for j in range(MDOF)]
                self.nodfat[node] = nf
                for (j, k) in enumerate(nfs):
                    if k:
                        active_dof[j] = j
        self.active_dof = array([x for x in active_dof if x is not None])

        # TOTAL NUMBER OF DEGREES OF FREEDOM
        self.numdof = sum(count_digits(p) for p in self.nodfat)

        # NODE FREEDOM MAP TABLE
        self.nodfmt = zeros(self.numnod, dtype=int)
        self._dofmap = {}
        dof = 0
        nodfmt = [0]
        for i in range(self.numnod):
            for (j, k) in enumerate(self.nodfat[i]):
                if not k: continue
                self._dofmap[i,j] = dof
                dof += 1
            nodfmt.append(dof)
        self.nodfmt = array(nodfmt[:-1], dtype=int)

        # ELEMENT FREEDOM TABLE
        self.eftab = self._element_freedom_table()

        self._setup = True

    def dofmap(self, inode, dof):
        return self._dofmap.get((inode,dof))

    def _check_element_validity(self):
        pass

    def initialize_steps(self):

        node_labels = sorted(self.mesh.nodmap, key=lambda k: self.mesh.nodmap[k])

        self.steps = step_repository(self)
        step = self.steps.InitialStep('Step-0')
        for (nodes, dof) in self.pr_bc:
            step.assign_prescribed_bc(nodes, dof, amplitude=0.)

        frame = step.frames[0]

        # NODE DATA
        nd = self.dimensions
        if T in self.active_dof:
            frame.FieldOutput(SCALAR, 'Q', NODE, node_labels)
        frame.FieldOutput(SCALAR, 'T', NODE, node_labels)
        frame.FieldOutput(VECTOR, 'U', NODE, node_labels, ncomp=self.dimensions)
        frame.FieldOutput(VECTOR, 'RF', NODE, node_labels, ncomp=self.dimensions)

        a = in1d((TX,TY,TZ), self.active_dof)
        if any(a):
            n = len([x for x in a if x])
            frame.FieldOutput(VECTOR, 'R', NODE, node_labels, ncomp=n)
            frame.FieldOutput(VECTOR, 'M', NODE, node_labels, ncomp=n)

        if self.initial_temp:
            itemp = self.get_initial_temperature()
            frame.field_outputs['T'].add_data(itemp)

        # ELEMENT DATA
        for eb in self.mesh.element_blocks:

            if not eb.eletyp.variables():
                continue

            ielems = [self.mesh.elemap[xel] for xel in eb.labels]
            elems = self.elements[ielems]

            if eb.eletyp.num_integration():
                position = INTEGRATION_POINT
            else:
                position = ELEMENT_CENTROID

            for variable in eb.eletyp.variables():
                if len(variable) == 2:
                    name, vtype = variable
                    idata = None
                elif len(variable) == 3:
                    name, vtype, idata = variable

                if idata is not None:
                    if idata == 1 and vtype == SYMTENSOR:
                        # IDENTITY
                        idata = array([1.]*elems[0].ndir+[0.]*elems[0].nshr)
                    elif idata == 1 and vtype == TENSOR:
                        idata = eye(elems[0].ndir)

                frame.FieldOutput(vtype, name, position, eb.labels,
                                  ndir=elems[0].ndir, nshr=elems[0].nshr,
                                  eleblk=eb.name, ngauss=elems[0].num_integration(),
                                  elements=elems, ncomp=self.dimensions, data=idata)

        frame.converged = True
        return

    def format_dof(self, dofs):
        # CONSTRUCT DISPLACEMENT AND ROTATION VECTORS
        d1 = len([x for x in self.active_dof if x in (X,Y,Z)])
        u = zeros((self.numnod, d1))

        d2 = len([x for x in self.active_dof if x in (TX,TY,TZ)])
        r = zeros((self.numnod, d2))

        if T in self.active_dof:
            temp = zeros(self.numnod)
        else:
            temp = None

        for n in range(self.numnod):
            ix, ui, ri = 0, 0, 0
            for j in range(MDOF):
                if self.nodfat[n,j] > 0:
                    ii = self.nodfmt[n] + ix
                    if j in (X,Y,Z):
                        u[n,ui] = dofs[ii]
                        ui += 1
                    elif j in (TX,TY,TZ):
                        r[n,ri] = dofs[ii]
                        ri += 1
                    else:
                        temp[n] = dofs[ii]
                    ix += 1
        return u, r, temp

    def _element_freedom_table(self):
        eftab = []
        for el in self.elements:
            eft = zeros(sum(count_digits(nfs) for nfs in el.signature), dtype=int)
            k, count = 0, 0
            for (i, inode) in enumerate(el.inodes):
                ix, sx = 0, zeros(MDOF, dtype=int)
                nfs1 = self.nodfat[inode]
                for j in range(MDOF):
                    if nfs1[j] > 0:
                        sx[j] = ix
                        ix += 1
                nfs2 = el.signature[i]
                for j in range(MDOF):
                    if nfs2[j] > 0:
                        if nfs1[j] > 0:
                            eft[k] = self.nodfmt[inode] + sx[j]
                            count += 1
                        k += 1
            if all(eft==0.):
                raise UserInputError('ZERO ENTRY IN EFTAB FOR '
                                     'ELEMENT {0}'.format(el.label))
            eftab.append(eft)
        return eftab

    def snapshot(self, step=None):

        if step is None:
            for step in self.steps.values():
                self.snapshot(step)
                if step.written:
                    break
            return

        if step.written:
            return

        self.exofile.snapshot(step)
        step.written = 1

    def apply_bc(self, K, F, doftags, dofvals, u=None, du=None):
        """
        .. _apply_bc:

        Apply boundary conditions to the global stiffness ``K`` and global
        force ``F``.

        Parameters
        ----------
        K : ndarray
            Global stiffness
        F : ndarray
            Global force

        Returns
        -------
        Kbc, Fbc : ndarray
            Boundary condition modified stiffness and force

        Notes
        -----
        Boundary conditions are applied in such a way that ``K`` remains
        symmetric by transferring columns associated with known degrees of
        freedom to ``F``. This method is intended to be called in the
        application code's ``Solve`` method.

        """
        if  u is None:  u = zeros(self.numdof)
        if du is None: du = zeros(self.numdof)

        # COPY THE GLOBAL ARRAYS
        Kbc, Fbc = K.copy(), F.copy()

        # DIRICHLET BOUNDARY CONDITIONS
        ubc = []
        for (i, I) in enumerate(doftags):
            u_cur = u[I] + du[I]
            ufac = dofvals[i] - u_cur
            ubc.append(ufac)
            Fbc -= [K[k,I] * ufac for k in range(self.numdof)]
            Kbc[I,:] = Kbc[:,I] = 0.
            Kbc[I,I] = 1.
        Fbc[doftags] = ubc
        return Kbc, Fbc

    # ----------------------------------------------------------------------- #
    # --- MATERIAL MODELS --------------------------------------------------- #
    # ----------------------------------------------------------------------- #
    def create_material(self, name, **kwargs):
        """Create an empty material object.

        Parameters
        ----------
        name : str
            The name of the material

        Notes
        -----
        The empty material is put in the self.materials container and can be
        referenced as self.material[name]

        See Also
        --------
        pyfem.material._material.Material

        """
        if name in self.materials:
            raise UserInputError('DUPLICATE MATERIAL {0!r}'.format(name))
        self.materials[name] = Material(name, **kwargs)
        return self.materials[name]

    def assign_prescribed_bc(self, nodes, dof):
        if self.steps is not None:
            raise UserInputError('Boundary conditions must be assigned to steps '
                                 'after creation of first step')
        self.pr_bc.append((nodes, dof))

    def fix_nodes(self, nodes):
        if self.steps is not None:
            raise UserInputError('Boundary conditions must be assigned to steps '
                                 'after creation of first step')
        self.pr_bc.append((nodes, ALL))
    fix_dofs = fix_nodes

    def pin_nodes(self, nodes):
        if self.steps is not None:
            raise UserInputError('Boundary conditions must be assigned to steps '
                                 'after creation of first step')
        self.pr_bc.append((nodes, PIN))

    def assign_initial_temperature(self, nodes, amplitude):
        if self.steps is not None:
            raise UserInputError('Intial temperatures must be assigned '
                                 'before creating first step')
        self.initial_temp.append((nodes, amplitude))

    def get_initial_temperature(self):
        itemp = zeros(self.numnod)
        for (nodes, amplitude) in self.initial_temp:
            inodes = self.mesh.get_internal_node_ids(nodes)
            if hasattr(amplitude, '__call__'):
                # AMPLITUDE IS A FUNCTION
                a = amplitude(self.mesh.coord[inodes])
            elif not is_listlike(amplitude):
                # CREATE A SINGLE AMPLITUDE FOR EACH NODE
                a = ones(len(inodes)) * amplitude
            else:
                if len(amplitude) != len(inodes):
                    raise UserInputError('INCORRECT AMPLITUDE LENGTH')
                # AMPLITUDE IS A LIST OF AMPLITUDES
                a = asarray(amplitude)
            itemp[inodes] = a
        return itemp

    # ----------------------------------------------------------------------- #
    # --- STEPS ------------------------------------------------------------- #
    # ----------------------------------------------------------------------- #
    def unique_step_name(self):
        i = len(self.steps)
        while 1:
            name = 'Step-{0}'.format(i)
            if name not in self.steps:
                break
            i += 1
            continue
        return name

    def _validate_step1(self, nlgeom=False, density=None):
        # VALIDATE INPUT
        for eb in self.mesh.element_blocks:
            iel = self.mesh.elemap[eb.labels[0]]
            el = self.elements[iel]
            if el.material.model.requires:
                if 'nlgeom' in el.material.model.requires and not nlgeom:
                    name = el.material.model.name
                    raise UserInputError('MATERIAL {0!r} REQUIRES '
                                         'nlgeom=True'.format(name.upper()))
            if density and not el.material.density:
                raise UserInputError('STEP REQUIRES MATERIAL DENSITY')

            if not any(el.signature[0][:3]):
                raise UserInputError('STEP REQUIRES ELEMENTS WITH '
                                     'DISPLACEMENT DEGREES OF FREEDOM')

    def _validate_step2(self):
        # VALIDATE INPUT
        for eb in self.mesh.element_blocks:
            iel = self.mesh.elemap[eb.labels[0]]
            el = self.elements[iel]
            if not el.signature[0][T]:
                raise UserInputError('STEP REQUIRES ELEMENTS WITH '
                                     'TEMPERATURE DEGREE OF FREEDOM')
            if any(el.signature[0][:3]):
                logging.warn('STEP WILL IGNORE DISPLACEMENT DEGREES OF FREEDOM')

    def create_static_step(self, name=None, period=1., **kwds):

        if self.steps is None:
            self.setup()
            self.initialize_steps()

        # VALIDATE INPUT
        self._validate_step1(nlgeom=kwds.get('nlgeom',False))

        if name is None:
            name = self.unique_step_name()

        if name in self.steps:
            raise UserInputError('Duplicate step name {0!r}'.format(name))

        step = self.steps.create_static_step(name, period, **kwds)
        return step

    def create_dynamic_step(self, name=None, period=1., **kwds):

        if period is None:
            raise UserInputError('DYNAMIC STEP REQUIRES PERIOD')

        if self.steps is None:
            self.setup()
            self.initialize_steps()

        # VALIDATE INPUT
        self._validate_step1(nlgeom=kwds.get('nlgeom'), density=True)

        if name is None:
            name = self.unique_step_name()

        if name in self.steps:
            raise UserInputError('Duplicate step name {0!r}'.format(name))

        step = self.steps.create_dynamic_step(name, period, **kwds)
        return step

    def create_heat_transfer_step(self, name=None, period=1.):
        if self.steps is None:
            self.setup()
            self.initialize_steps()

        # VALIDATE INPUT
        self._validate_step2()

        if name is None:
            name = self.unique_step_name()

        if name in self.steps:
            raise UserInputError('Duplicate step name {0!r}'.format(name))

        step = self.steps.create_heat_transfer_step(name, period=period)
        return step

    # ----------------------------------------------------------------------- #
    # --- ELEMENT BLOCKS AND SETS-------------------------------------------- #
    # ----------------------------------------------------------------------- #
    def create_element_block(self, name, elements):
        """Create an element block and assign elements to it

        Parameters
        ----------
        name : str
            The name of the element block
        elements : int, list, or symbolic constant
            Element label, list of element labels, or symbolic constant

        See Also
        --------
        felab.mesh.Mesh.element_block

        """
        if self.mesh is None:
            raise UserInputError('MESH MUST FIRST BE CREATED')
        blk = self.mesh.create_element_block(name, elements)
        return blk

    def assign_properties(self, blknam, eletyp, elemat, **elefab):
        """Assign properties to elements in an element block

        Parameters
        ----------
        blknam : str
            The name of the element block
        eletyp : object
            The element type (uninstantiated class)
        elemat : str or Material
            The name of the material model, or a material model
        elefab : dict
            Element fabrication properties

        Notes
        -----
        Before this method is called:

        - elements must be assigned to element blocks; and
        - the material model must be created with the Material method.

        Not all element types require element fabrication properties. For
        example, plane stress-displacement elements require the thickness
        ``t`` be specified but plane heat transfer elements do not

        """
        if self.mesh is None:
            raise UserInputError('MESH MUST FIRST BE CREATED')
        if elemat in self.materials:
            elemat = self.materials[elemat]
        elif isinstance(elemat, Material):
            if elemat.name not in self.materials:
                self.materials[elemat.name] = elemat
        else:
            raise UserInputError('NO SUCH MATERIAL {0!r}'.format(elemat))
        for blk in self.mesh.element_blocks:
            if blk.name.upper() == blknam.upper():
                break
        else:
            raise UserInputError('NO SUCH ELEMENT BLOCK {0!r}'.format(blknam))
        blk.eletyp = eletyp
        if eletyp.nodes != blk.elecon.shape[1]:
            raise UserInputError('NODE TYPE NOT CONSISTENT WITH ELEMENT BLOCK')

        if elefab:
            # ELEMENT FABRICATION PROPERTIES GIVEN, MAKE SURE THERE IS ONE
            # PROPERTY PER ELEMENT
            for (key, val) in elefab.items():
                if not is_listlike(val) or len(val) != len(blk.labels):
                    elefab[key] = [val] * len(blk.labels)
                else:
                    elefab[key] = val

        for (i, xel) in enumerate(blk.labels):
            iel = self.mesh.elemap[xel]
            elenod = blk.elecon[i]
            elecoord = self.mesh.coord[elenod]
            kwds = {}
            for (key, val) in elefab.items():
                kwds[key] = val[i]
            self.elements[iel] = eletyp(xel, elenod, elecoord, elemat, **kwds)

    def create_node_set(self, name, region):
        """Create a node set

        Parameters
        ----------
        name : str
            Name for this element set
        region : int, list, or symbolic constant
            Node label, list of node labels, or symbolic constant

        See Also
        --------
        felab.mesh.Mesh.node_set

        """
        if self.mesh is None:
            raise UserInputError('MESH MUST FIRST BE CREATED')
        self.mesh.create_node_set(name, region)

    def create_side_set(self, name, surface):
        """Create a surface

        Parameters
        ----------
        name : str
            Name for this element set
        surface : list, list of list, or symbolic constant
            Element/face, list of element/face, or symbolic constant

        See Also
        --------
        felab.mesh.Mesh.side_set

        """
        if self.mesh is None:
            raise UserInputError('MESH MUST FIRST BE CREATED')
        self.mesh.create_side_set(name, surface)

    def create_element_set(self, name, region):
        """Create an element set

        Parameters
        ----------
        name : str
            Name for this element set
        region : int, list, or symbolic constant
            Element label, list of element labels, or symbolic constant

        See Also
        --------
        felab.mesh.Mesh.element_set

        """
        if self.mesh is None:
            raise UserInputError('MESH MUST FIRST BE CREATED')
        self.mesh.create_element_set(name, region)

    def _get_field(self, key):
        key1 = key.lower()
        if key1 in ('u', 'ux', 'uy', 'uz'):
            key1 = 'displ' + key1[1:]
        for (name, field) in self.steps.last.frames[-1].field_outputs.items():
            if key1 == name.lower() or key.lower() == name.lower():
                if field.type != SCALAR:
                    comps = ','.join(key+comp for comp in field.components)
                    msg = 'NON SCALAR PLOTTING REQUIRES COMPONENTS BE SPECIFIED. '
                    msg += 'TRY ONE OF {0}'.format(comps)
                    raise UserInputError(msg)
                return field.data
            if key.lower() == name.lower():
                key1 = key.lower()
            if key1 in field.keys:
                if field.position in (ELEMENT, INTEGRATION_POINT):
                    raise NotImplementedError('PLOTTING ELEMENT DATA NOT DONE')
                return field.data[:,field.keys.index(key1)]
        raise UserInputError('NO SUCH FIELD {0!r}'.format(key))

    def Plot2D(self, deformed=False, color=None, colorby=None, scale=1., **kwds):
        """Create a 2D plot

        Parameters
        ----------
        deformed : bool, optional {False,True}
            Plot the deformed mesh if True
        color : matplotlib color
        kwds : dict
            kwds passed to felab.mesh.Plot2D

        Returns
        -------
        ax : axes object
            The plot axes

        See Also
        --------
        felab.mesh.Mesh.Plot2D

        """
        assert self.dimensions == 2
        if self.dimensions != 2:
            raise UserInputError('Plot2D IS ONLY APPLICABLE TO 2D PROBLEMS')
        xy = array(self.mesh.coord)
        if deformed:
            xy += scale * self.steps.last.dofs.reshape(xy.shape)
        elecon = []
        for blk in self.mesh.element_blocks:
            if (blk.eletyp.dimensions, blk.eletyp.nodes) == (2,8):
                raise NotImplementedError('PLOTTING VALID ONLY FOR LINEAR ELEMENT')
            else:
                elecon.extend(blk.elecon)

        if colorby is not None and is_stringlike(colorby):
            colorby = self._get_field(colorby)
        return self.mesh.Plot2D(xy=xy, elecon=array(elecon), color=color,
                                colorby=colorby, **kwds)

    def write_results(self):
        """Write the finite element results to a file"""
        for (name, step) in self.steps.items():
            self.snapshot(step)
        self.fh.close()