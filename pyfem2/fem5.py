""".pft.py: Plane Beam Column Truss application code.

"""
from numpy import *
from numpy.linalg import solve, LinAlgError

from .constants import *
from .utilities import linsolve
from .finite_element_model import FiniteElementModel
from .elemlib import ElasticLink2D2, PlaneBeamColumn

# --------------------------------------------------------------------------- #
# -------------------------- APPLICATION CODE ------------------------------- #
# --------------------------------------------------------------------------- #
class PlaneBeamColumnTrussModel(FiniteElementModel):
    dimensions = 2

    def Solve(self):
        # ACTIVE DOF SET DYNAMICALLY
        self.setup((ElasticLink2D2, PlaneBeamColumn))

        # ASSEMBLE THE GLOBAL STIFFNESS AND FORCE
        du = zeros(self.numdof)
        K, rhs = self.assemble(self.dofs, du)
        Kbc, Fbc = self.apply_bc(K, rhs)

        # SOLVE
        self.dofs[:] = linsolve(Kbc, Fbc)

        # TOTAL FORCE, INCLUDING REACTION, AND REACTION
        R = dot(K, self.dofs) - rhs

        Q = self.external_force_array()
        R = zeros(self.numdof)
        U, R, Urot, Rrot = self.format_displacements_and_reactions(self.dofs, R)

        frame = self.steps.last.Frame(1.)
        frame.field_outputs['U'].add_data(U)
        frame.field_outputs['R'].add_data(R)
        frame.converged = True

        self.u = U

    def format_displacements_and_reactions(self, u, R):
        # CONSTRUCT DISPLACEMENT AND ROTATION VECTORS
        ut, rt = zeros((self.numnod, 2)), zeros((self.numnod, 2))
        ur, rr = zeros(self.numnod), zeros(self.numnod)
        for n in range(self.numnod):
            ix = 0
            for j in range(MDOF):
                if self.nodfat[n,j] > 0:
                    ii = self.nodfmt[n] + ix
                    if j <= 2:
                        ut[n,j] = u[ii]
                        rt[n,j] = R[ii]
                    else:
                        # THIS WOULD NEED MODIFYING IF 3D BEAMS WERE ALLOWED
                        ur[n] = u[ii]
                        rr[n] = R[ii]
                    ix += 1
        return ut, rt, ur, rr
