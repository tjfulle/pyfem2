from numpy import *
from isoplib import IsoPElement

__all__ = ['PlaneStressTria3', 'PlaneStrainTria3']

# --------------------------------------------------------------------------- #
# --------------------- TRIANGLE ISOPARAMETRIC ELEMENTS --------------------- #
# --------------------------------------------------------------------------- #
class IsoPTria3(IsoPElement):
    """3-node isoparametric element

    Notes
    -----
    Node and element face numbering


            2
            | \
       [2]  |  \ [1]
            |   \
            0----1
              [0]

    """
    signature = 1100000
    numdim, numnod, ndof = 2, 3, 2
    edges = array([[0, 1], [1, 2], [2, 0]])
    gaussp = None   # COMPLETE: FILL IN THE ARRAY OF GAUSS POINTS
    gaussw = None   # COMPLETE: FILL IN THE ARRAY OF GAUSS WEIGHTS
    cp = array([1, 1], dtype=float64) / 3.
    xp = array([[0, 0], [1, 0], [0, 1]], dtype=float64)

    def __init__(self, label, elenod, elecoord, elemat, **elefab):
        self.label = label
        self.nodes = elenod
        self.xc = elecoord
        self.material = elemat
        self.t = elefab.get('t')
        if self.t is None:
            raise ValueError('Incorrect number of element fabrication properties')

    @property
    def area(self):
        x, y = self.xc[:, [0, 1]].T
        a = .5 * (x[0] * (y[1] - y[2]) +
                  x[1] * (y[2] - y[0]) +
                  x[2] * (y[0] - y[1]))
        return a

    @property
    def volume(self):
        return self.t * self.area

    def shape(self, xi):
        # COMPLETE: DEFINE THE APPROPRIATE SHAPE FUNCTIONS
        Ne = None
        return Ne

    def shapegrad(self, xi):
        # COMPLETE: DEFINE THE APPROPRIATE SHAPE FUNCTION DERIVATIVES
        dN = None
        return dN

    def bshape(self, xi):
        # COMPLETE: DEFINE THE APPROPRIATE BOUNDARY SHAPE FUNCTIONS
        bN = None
        return bN

    def bshapegrad(self, xi):
        # COMPLETE: DEFINE THE APPROPRIATE BOUNDARY SHAPE FUNCTION DERIVATIVES
        dbN = None
        return dbN

# --------------------------------------------------------------------------- #
# ------------------------ USER ELEMENT TYPES ------------------------------- #
# --------------------------------------------------------------------------- #
class PlaneStressTria3(IsoPTria3):
    ndir, nshr = 2, 1
    def bmatrix(self, dN):
        # COMPLETE: DEFINE THE B MATRIX FOR PLANE STRESS
        B = None
        return B

class PlaneStrainTria3(IsoPTria3):
    ndir, nshr = 3, 1
    def bmatrix(self, dN):
        # COMPLETE: DEFINE THE B MATRIX FOR PLANE STRAIN
        B = None
        return B
