import numpy as np
import scipy as sp
from scipy.sparse import issparse, isspmatrix_coo, isspmatrix_csr, isspmatrix_csc
from scipy.sparse.linalg import spsolve, bicgstab, gmres, lgmres, cg, spilu, LinearOperator, onenormest
from scipy.io import savemat, loadmat
from subprocess import call
import os


class LinearSolver(object):
    """Base class for all linear sparse direct and iterative solvers"""

    def __init__(self,linear_solver="direct", linear_solver_type="umfpack",
        apply_preconditioner=False, preconditioner="amg_smoothed_aggregation", 
        iterative_solver_tolerance=1.0e-12, reduce_matrix_bandwidth=False,
        out_of_core=False):
        """

            input:
                linear_solver:          [str] type of solver either "direct", 
                                        "iterative" or "multigrid"

                linear_solver_type      [str] type of direct or linear solver to
                                        use, for instance "umfpack", "superlu" or 
                                        "mumps" for direct solvers, or "cg", "gmres"
                                        etc for iterative solvers or "amg" for algebraic
                                        multigrid solver. See WhichSolvers method for
                                        the complete set of available linear solvers 

                preconditioner:         [str] either "amg_smoothed_aggregation" for 
                                        a preconditioner based on algebraic multigrid
                                        or "incomplete_lu" for scipy's spilu linear 
                                        operator


        """          

        self.is_sparse = True
        self.solver_type = linear_solver
        self.solver_subtype = linear_solver_type
        self.requires_cuthill_mckee = reduce_matrix_bandwidth
        self.iterative_solver_tolerance = iterative_solver_tolerance
        self.apply_preconditioner = apply_preconditioner
        self.preconditioner_type = preconditioner
        self.out_of_core = False

        self.has_amg_solver = True
        try:
            import pyamg
        except ImportError:
            self.has_amg_solver = False

        self.has_umfpack = True
        try:
            from scikits.umfpack import spsolve
        except ImportError:
            self.has_umfpack = False

        self.switcher_message = False

        # self.analysis_type = "static"
        # self.analysis_nature = "linear"

    def SetSolver(self,linear_solver="direct", linear_solver_type="umfpack",
        apply_preconditioner=False, preconditioner="amg_smoothed_aggregation", 
        iterative_solver_tolerance=1.0e-12, reduce_matrix_bandwidth=False):
        """

            input:
                linear_solver:          [str] type of solver either "direct", 
                                        "iterative" or "multigrid"

                linear_solver_type      [str] type of direct or linear solver to
                                        use, for instance "umfpack", "superlu" or 
                                        "mumps" for direct solvers, or "cg", "gmres"
                                        etc for iterative solvers or "amg" for algebraic
                                        multigrid solver. See WhichSolvers method for
                                        the complete set of available linear solvers 

                preconditioner:         [str] either "amg_smoothed_aggregation" for 
                                        a preconditioner based on algebraic multigrid
                                        or "incomplete_lu" for scipy's spilu linear 
                                        operator


        """ 

        self.solver_type = linear_solver
        self.solver_subtype = "umfpack"
        self.iterative_solver_tolerance = iterative_solver_tolerance
        self.apply_preconditioner = apply_preconditioner
        self.requires_cuthill_mckee = reduce_matrix_bandwidth

    @property
    def WhichLinearSolver(self):
        return self.solver_type, solver_subtype

    @property
    def WhichLinearSolvers(self):
        return {"direct":["superlu","umfpack","mumps"],
            "iterative":["cg","bicg","cgstab","bicgstab"
            "gmres","lgmres"],"multigrid":["amg"]}


    def GetPreconditioner(self,A, type="amg_smoothed_aggregation"):
        """Applies a suitable preconditioner to sparse matrix A
            based on algebraic multigrid of incomplete LU/Cholesky factorisation

            input:
                A:                      [csc_matrix or csc_matrix]
                type:                   [str] either "amg_smoothed_aggregation" for 
                                        a preconditioner based on algebraic multigrid
                                        or "incomplete_lu" for scipy's spilu linear 
                                        operator

            returns:                    A preconditioner that can be used in conjunction
                                        with scipy's sparse linear iterative solvers 
                                        (the M keyword in scipy's iterative solver) 
        """

        if not (isspmatrix_csc(A) or isspmatrix_csr(A)):
            raise TypeError("Matrix must be in CSC or CSR sparse format for preconditioning")

        ml = smoothed_aggregation_solver(A)
        return ml.aspreconditioner()


    def GetCuthillMcKeePermutation(self,A):
        """Applies Cuthill-Mckee permutation to reduce the sparse matrix bandwidth

            input:
                A:                    [csc_matrix or csc_matrix]

            returns:
                perm:                 [1D array] of permutation such that A(perm,perm)
                                      has its non-zero elements closer to the diagonal
        """

        if not (isspmatrix_csc(A) or isspmatrix_csr(A)):
            raise TypeError("Matrix must be in CSC or CSR sparse format "
                "for Cuthill-McKee permutation")

        if int(sp.__version__.split('.')[1]) >= 15:
            from scipy.sparse.csgraph import reverse_cuthill_mckee
            perm = reverse_cuthill_mckee(A)
        else:
            from Florence.Tensor import symrcm
            perm = symrcm(A)

        return perm



    def Solve(self,A,b):
        """Solves the linear system of equations"""


        # DECIDE IF THE SOLVER TYPE IS APPROPRIATE FOR THE PROBLEM
        if self.switcher_message is False:
            if b.shape[0] > 100000:
                self.solver_type = "multigrid"
                self.solver_subtype = "amg"
                print 'Large system of equations. Switching to algebraic multigrid solver'
            # elif mesh.points.shape[0]*MainData.nvar > 50000 and MainData.C < 4:
                # self.solver_type = "direct"
                # self.solver_subtype = "MUMPS"
                # print 'Large system of equations. Switching to MUMPS solver'
            else:
                self.solver_type = "direct"
                self.solver_subtype = "umfpack"


        if self.solver_type == 'direct':
            # CALL DIRECT SOLVER
            if self.solver_subtype=='umfpack' and self.has_umfpack:
                if A.dtype != np.float64:
                    A = A.astype(np.float64)

                sol = spsolve(A,b,permc_spec='MMD_AT_PLUS_A',use_umfpack=True)

            elif sub_type=='mumps' and self.has_mumps:
                # CALL JULIA'S MUMPS WRAPPER
                pwd = os.path.dirname(os.path.realpath(__file__))

                A = A.tocoo()
                # SAVE I, J & V TO FILES
                JuliaDict = {'rowIndA':A.row.astype(np.int64)+1,
                            'colPtrA':A.col.astype(np.int64)+1,
                            'valuesA':A.data,'shapeA':A.shape,
                            'rhs':b}

                savemat(pwd+"/JuliaDict.mat",JuliaDict)

                del A, b

                mumps_failed = False
                try:
                    call(["julia",pwd+"/JuliaMUMPS.jl"])
                except AssertionError:
                    mumps_failed = True

                if not mumps_failed:
                    sol = np.loadtxt(pwd+"/solution")
                    os.remove(pwd+"/solution")
                
                # FromJulia = loadmat(pwd+"JuliaDict.mat")
                # sol = FromJulia["sol"]

                # REMOVE THE FILES
                os.remove(pwd+"/JuliaDict.mat")

            else:
                # FOR 'super_lu'
                sol = spsolve(A,b,permc_spec='MMD_AT_PLUS_A',use_umfpack=True)

        elif self.solver_type == "iterative":
            # CALL ITERATIVE SOLVER
            # sol = bicgstab(A,b,tol=tol)[0]
            # sol = gmres(A,b,tol=tol)[0]
            sol = cg(A,b,tol=1e-04)[0]

            # PRECONDITIONED ITERATIVE SOLVER - CHECK
            # P = spilu(A, drop_tol=1e-5)
            # M_x = lambda x: P.solve(x)
            # n = A.shape[0]
            # m = A.shape[1]
            # M = LinearOperator((n * m, n * m), M_x)
            # sol = lgmres(A, b, tol=1e-4, M=M)[0]

        elif self.solver_type == "multigrid":
            if self.has_amg_solver is False:
                raise ImportError('A multigrid solver was not found')

            if A.dtype != b.dtype:
                # DOWN-CAST
                b = b.astype(A.dtype)

            if not isspmatrix_csr(A):
                A = A.tocsr()
            
            # AMG METHOD
            ml = ruge_stuben_solver(A)
            sol = ml.solve(b,tol=self.iterative_solver_tolerance)

            # EXPLICIT CALL TO KYROLOV SOLVERS WITH AMG PRECONDITIONER
            # THIS IS TYPICALLY FASTER BUT THE TOLERANCE NEED TO BE SMALLER, TYPICALLY 1e-10
            # ml = smoothed_aggregation_solver(A)
            # M = ml.aspreconditioner()
            # if tol > 1e-9:
            #     tol = 1e-10
            # sol, info = gmres(A, b, M=M, tol=tol)

        return sol

    def GetConditionNumber(self,A):
        self.matrix_condition_number = onenormest(K_b)
        return self.matrix_condition_number