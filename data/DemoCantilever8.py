from pyfem2 import *
nodtab = [[1, 0.0, 0.0],
          [2, 0.5, 0.0],
          [3, 1.0, 0.0],
          [4, 1.5, 0.0],
          [5, 2.0, 0.0],
          [6, 2.5, 0.0],
          [7, 3.0, 0.0],
          [8, 3.5, 0.0],
          [9, 4.0, 0.0],
          [10, 4.5, 0.0],
          [11, 5.0, 0.0],
          [12, 5.5, 0.0],
          [13, 6.0, 0.0],
          [14, 6.5, 0.0],
          [15, 7.0, 0.0],
          [16, 7.5, 0.0],
          [17, 8.0, 0.0],
          [22, 0.0, 0.25],
          [23, 1.0, 0.25],
          [24, 2.0, 0.25],
          [25, 3.0, 0.25],
          [26, 4.0, 0.25],
          [27, 5.0, 0.25],
          [28, 6.0, 0.25],
          [29, 7.0, 0.25],
          [30, 8.0, 0.25],
          [33, 0.0, 0.5],
          [34, 0.5, 0.5],
          [35, 1.0, 0.5],
          [36, 1.5, 0.5],
          [37, 2.0, 0.5],
          [38, 2.5, 0.5],
          [39, 3.0, 0.5],
          [40, 3.5, 0.5],
          [41, 4.0, 0.5],
          [42, 4.5, 0.5],
          [43, 5.0, 0.5],
          [44, 5.5, 0.5],
          [45, 6.0, 0.5],
          [46, 6.5, 0.5],
          [47, 7.0, 0.5],
          [48, 7.5, 0.5],
          [49, 8.0, 0.5],]
eletab = [[1, 1, 3, 35, 33, 2, 23, 34, 22],
          [2, 3, 5, 37, 35, 4, 24, 36, 23],
          [3, 5, 7, 39, 37, 6, 25, 38, 24],
          [4, 7, 9, 41, 39, 8, 26, 40, 25],
          [5, 9, 11, 43, 41, 10, 27, 42, 26],
          [6, 11, 13, 45, 43, 12, 28, 44, 27],
          [7, 13, 15, 47, 45, 14, 29, 46, 28],
          [8, 15, 17, 49, 47, 16, 30, 48, 29],]

def RunModel():
    mesh = Mesh(nodtab=nodtab, eletab=eletab)
    V = FiniteElementModel(mesh=mesh)
    mat_1 = Material('Material-1', elastic={'Nu': 0.3, 'E': 100.0})
    V.ElementBlock('ElementBlock-1', (1, 2, 3, 4, 5, 6, 7, 8))
    V.AssignProperties('ElementBlock-1', PlaneStressQuad8, mat_1)
    step = V.StaticStep() #solver=NEWTON)
    step.PrescribedBC( 1, (X,Y))
    step.PrescribedBC(22, (X,Y))
    step.PrescribedBC(33, (X,Y))
    step.ConcentratedLoad(49, Y, 0.01)
    step.run()
    V.WriteResults()

if __name__ == '__main__':
    RunModel()
