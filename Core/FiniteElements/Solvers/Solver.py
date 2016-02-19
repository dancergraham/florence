import os, sys
from time import time
import numpy as np
from copy import deepcopy

from Core.FiniteElements.Assembly import *
from Core.FiniteElements.ApplyDirichletBoundaryConditions import *
from Core.FiniteElements.PostProcess import *
# from Core.FiniteElements.StaticCondensationGlobal import *
from Core.FiniteElements.InitiateNonlinearAnalysisData import *
# from Core.FiniteElements.Solvers.DynamicSolver import *
from Core.FiniteElements.Solvers.StaticSolver import *
from Core.FiniteElements.Solvers.IncrementalLinearElasticitySolver import *

def MainSolver(MainData,mesh):

    # INITIATE DATA FOR NON-LINEAR ANALYSIS
    NodalForces, Residual = InitiateNonlinearAnalysisData(MainData,mesh)
    # SET NON-LINEAR PARAMETERS
    Tolerance = MainData.AssemblyParameters.NRTolerance
    LoadIncrement = MainData.AssemblyParameters.LoadIncrements
    ResidualNorm = { 'Increment_'+str(Increment) : [] for Increment in range(0,LoadIncrement) }
    
    # ALLOCATE FOR SOLUTION FIELDS
    # TotalDisp = np.zeros((mesh.points.shape[0],MainData.nvar,LoadIncrement),dtype=np.float64)
    TotalDisp = np.zeros((mesh.points.shape[0],MainData.nvar,LoadIncrement),dtype=np.float32)

    # PRE-ASSEMBLY
    print 'Assembling the system and acquiring neccessary information for the analysis...'
    tAssembly=time()

    # FIND PURE NEUMANN (EXTERNAL) NODAL FORCE VECTOR
    # NeumannForces = AssemblyForces(MainData,mesh)
    # NeumannForces = AssemblyForces_Cheap(MainData,mesh)
    # NeumannForces = np.zeros((mesh.points.shape[0]*MainData.nvar,1),dtype=np.float64)
    NeumannForces = np.zeros((mesh.points.shape[0]*MainData.nvar,1),dtype=np.float32)
    # APPLY DIRICHELT BOUNDARY CONDITIONS AND GET DIRICHLET RELATED FORCES
    ColumnsIn, ColumnsOut, AppliedDirichlet = GetDirichletBoundaryConditions(mesh,MainData)
    # ALLOCATE FOR GEOMETRY - GetDirichletBoundaryConditions CHANGES THE MESH 
    # SO EULERX SHOULD BE ALLOCATED AFTERWARDS 
    Eulerx = np.copy(mesh.points)
    # FORCES RESULTING FROM DIRICHLET BOUNDARY CONDITIONS
    # DirichletForces = np.zeros((mesh.points.shape[0]*MainData.nvar,1),dtype=np.float64)
    DirichletForces = np.zeros((mesh.points.shape[0]*MainData.nvar,1),dtype=np.float32)

    # ADOPT A DIFFERENT PATH FOR INCREMENTAL LINEAR ELASTICITY
    if MainData.Fields == "Mechanics" and MainData.AnalysisType != "Nonlinear":     
        # MAKE A COPY OF MESH, AS MESH POINTS WILL BE OVERWRITTEN
        vmesh = deepcopy(mesh)
        TotalDisp = IncrementalLinearElasticitySolver(MainData,vmesh,TotalDisp,
            Eulerx,LoadIncrement,NeumannForces,ColumnsIn,ColumnsOut,AppliedDirichlet)
        del vmesh

        # ADD EACH INCREMENTAL CONTRIBUTION TO MAKE IT CONSISTENT WITH THE NONLINEAR ANALYSYS
        for i in range(TotalDisp.shape[2]-1,0,-1):
            TotalDisp[:,:,i] = np.sum(TotalDisp[:,:,:i+1],axis=2)

        return TotalDisp

    # ASSEMBLE STIFFNESS MATRIX AND TRACTION FORCES
    K,TractionForces = Assembly(MainData,mesh,Eulerx,np.zeros((mesh.points.shape[0],1),dtype=np.float64))[:2]
    
    # GET DIRICHLET FORCES
    DirichletForces = ApplyDirichletGetReducedMatrices(K,DirichletForces,ColumnsIn,ColumnsOut,
        AppliedDirichlet,MainData.Analysis,[])[2]

    if MainData.AnalysisType=='Nonlinear':
        print 'Finished all pre-processing stage. Time elapsed was', time()-tAssembly, 'sec'
    else:
        print 'Finished the assembly stage. Time elapsed was', time()-tAssembly, 'sec'


    if MainData.Analysis != 'Static':
        TotalDisp = DynamicSolver(LoadIncrement,MainData,K,M,DirichletForces,NeumannForces,NodalForces,
            Residual,ResidualNorm,mesh,TotalDisp,
            Eulerx,ColumnsIn,ColumnsOut,AppliedDirichlet)
    else:
        TotalDisp = StaticSolver(MainData,LoadIncrement,K,DirichletForces,NeumannForces,NodalForces,Residual,
            ResidualNorm,mesh,TotalDisp,Eulerx,ColumnsIn,ColumnsOut,AppliedDirichlet)


    MainData.NRConvergence = ResidualNorm

    return TotalDisp






