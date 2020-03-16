import numpy as np
from felab.mesh import rectilinear_mesh2d
from felab.constants import ALL


def test_compare_new_to_old(plot=False):
    a, b = 2.0, 1.0
    nx, ny = 3, 2
    corners = np.array([[0, 0], [a, 0], [a, b], [0, b]], dtype=float)
    mesh1 = rectilinear_mesh2d(3, 2, a, b, method=2)
    mesh8 = rectilinear_mesh2d(3, 2, a, b, method=2, order=2)
    mesh2 = rectilinear_mesh2d(3, 2, a, b)

    mesh1.create_element_block("EALL", ALL)
    mesh2.create_element_block("EALL", ALL)

    mesh8.create_element_block("EALL", ALL)
    c = np.array(
        [
            [0, 8, 10, 2, 5, 9, 6, 1],
            [2, 10, 12, 4, 6, 11, 7, 3],
            [8, 16, 18, 10, 13, 17, 14, 9],
            [10, 18, 20, 12, 14, 19, 15, 11],
            [16, 24, 26, 18, 21, 25, 22, 17],
            [18, 26, 28, 20, 22, 27, 23, 19],
        ]
    )
    assert np.allclose(mesh8.connectivity(), c)

    if plot:
        ax = mesh2.Plot2D(color="orange", label="Original", weight=3)
        mesh1.Plot2D(ax=ax, show=1, color="b", label="New")


if __name__ == "__main__":
    test_compare_new_to_old(plot=True)