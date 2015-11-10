from time import time
import numpy as np
import numpy.linalg as la
# from scipy.sparse.linalg import spsolve, cg, cgs, bicg, bicgstab, gmres, lgmres, minres
from scipy.sparse.linalg import spsolve, bicgstab 
from scipy.sparse.linalg import svds, eigsh, eigs, inv as spinv, onenormest
import copy

from Core.FiniteElements.Assembly import *
from Core.FiniteElements.PostProcess import * 
from Core.FiniteElements.ApplyDirichletBoundaryConditions import *

def LinearSolver(Increment,MainData,K,F,M,NodalForces,Residual,ResidualNorm,nmesh,TotalDisp,Eulerx,
			columns_in,columns_out,AppliedDirichletInc):

	# GET THE REDUCED ELEMENTAL MATRICES 
	# K_b, F_b, _, _ = ApplyLinearDirichletBoundaryConditions(K,F,columns_in,columns_out,AppliedDirichletInc,MainData.Analysis,M)
	K_b, F_b = ApplyLinearDirichletBoundaryConditions(K,Residual,columns_in,MainData.Analysis,M)[:2]
	
	# SOLVE THE SYSTEM
	# np.savetxt('/media/MATLAB/MeshingElasticity/F_now.dat',F_b)
	# np.savetxt('/home/roman/Desktop/MeshingElasticity2/F_b.dat',F)
	# np.savetxt('/home/roman/Desktop/MeshingElasticity2/K_b.dat',K.toarray())
	t_solver=time()
	if MainData.solve.type == 'direct':
		# CHECK FOR THE CONDITION NUMBER OF THE SYSTEM
		if Increment==MainData.AssemblyParameters.LoadIncrements-1:
			# MainData.solve.condA = np.linalg.cond(K_b.todense()) # REMOVE THIS
			MainData.solve.condA = onenormest(K_b) # REMOVE THIS
		# CALL DIRECT SOLVER
		sol = spsolve(K_b,-F_b,permc_spec='MMD_AT_PLUS_A',use_umfpack=True)
	else:
		# CALL ITERATIVE SOLVER
		sol = bicgstab(K_b,-F_b,tol=MainData.solve.tol)[0]
	print 'Finished solving the system. Time elapsed was', time()-t_solver
	
	# GET THE TOTAL SOLUTION AND ITS COMPONENTS SUCH AS UX, UY, UZ, PHI ETC
	dU = PostProcess().TotalComponentSol(MainData,sol,columns_in,columns_out,AppliedDirichletInc,0,F.shape[0]) 

	# UPDATE THE FIELDS
	TotalDisp[:,:,Increment] += dU

	# # LINEAR ELASTICITY IN STEPS
	# if MainData.LinearWithStep:
	# 	# UPDATE THE GEOMETRY
	# 	vmesh = copy.deepcopy(nmesh)
	# 	vmesh.points = nmesh.points + TotalDisp[:,:MainData.ndim,Increment]
	# 	Eulerx = np.copy(vmesh.points) 
	# 	K = Assembly(MainData,vmesh,Eulerx,np.zeros((nmesh.points.shape[0],1),dtype=np.float64))[0]

	# LINEARISED ELASTICITY WITH STRESS AND HESSIAN UPDATE
	if MainData.Prestress:
		
		# # UPDATE THE GEOMETRY
		# Eulerx = nmesh.points + TotalDisp[:,:MainData.ndim,Increment]			
		# # RE-ASSEMBLE - COMPUTE INTERNAL TRACTION FORCES (BE CAREFUL ABOUT THE -1 INDEX IN HERE)
		# K, TractionForces = Assembly(MainData,nmesh,Eulerx,TotalDisp[:,MainData.nvar-1,Increment].reshape(TotalDisp.shape[0],1))[:2]
		# # FIND THE RESIDUAL
		# Residual[columns_in] = TractionForces[columns_in] - NodalForces[columns_in]

		if Increment <MainData.AssemblyParameters.LoadIncrements-1:
			# UPDATE THE GEOMETRY
			Eulerx = nmesh.points + TotalDisp[:,:MainData.ndim,Increment]			
			# RE-ASSEMBLE - COMPUTE INTERNAL TRACTION FORCES (BE CAREFUL ABOUT THE -1 INDEX IN HERE)
			K, TractionForces = Assembly(MainData,nmesh,Eulerx,TotalDisp[:,MainData.nvar-1,Increment].reshape(TotalDisp.shape[0],1))[:2]
			# FIND THE RESIDUAL
			Residual[columns_in] = TractionForces[columns_in] - NodalForces[columns_in]
			print Increment

	print 'Load increment', Increment, 'for incrementally linearised elastic problem'

	# RETURNING K IS NECESSARY
	return TotalDisp, K