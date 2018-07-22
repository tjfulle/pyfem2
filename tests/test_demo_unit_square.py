import os
from felab import *

def UnitSquareDemo(plot=False):
    mesh = unit_square_mesh(nx=2, ny=2)
    mat = Material('Mat', elastic={'E': 1000, 'Nu': 0})

    V = fe_model(mesh=mesh)
    V.create_element_block('All', ALL)
    V.assign_properties('All', CPS4, mat)
    V.fix_nodes(ILO)

    step = V.create_static_step()
    step.assign_prescribed_bc(IHI, X, .1)
    step.run()
    step.print_stiffness_structure(style='latex')
    if plot:
        V.Plot2D(deformed=1, show=1)

    step = V.create_static_step()
    step.assign_prescribed_bc(IHI, X, 0)
    step.run()

    if plot:
        V.Plot2D(deformed=1, show=1)

def test(plot=False):
    UnitSquareDemo(plot=plot)

if __name__ == '__main__':
    test(plot=True)