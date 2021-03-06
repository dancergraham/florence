#include "_MaterialBase_.h"
#include "_LegendreTransform_.h"

template<typename U>
class _IsotropicElectroMechanics_107_: public _MaterialBase_<U> {
public:
    U mu1;
    U mu2;
    U mue;
    U lamb;
    U eps_1;
    U eps_2;
    U eps_e;

    _IsotropicElectroMechanics_107_() = default;

    FASTOR_INLINE
    _IsotropicElectroMechanics_107_(U mu1, U mu2, U mue, U lamb, U eps_1, U eps_2, U eps_e) {
        this->mu1 = mu1;
        this->mu2 = mu2;
        this->mue = mue;
        this->lamb = lamb;
        this->eps_1 = eps_1;
        this->eps_2 = eps_2;
        this->eps_e = eps_e;
    }

    FASTOR_INLINE
    void SetParameters(U mu1, U mu2, U mue, U lamb, U eps_1, U eps_2, U eps_e){
        this->mu1 = mu1;
        this->mu2 = mu2;
        this->mue = mue;
        this->lamb = lamb;
        this->eps_1 = eps_1;
        this->eps_2 = eps_2;
        this->eps_e = eps_e;
    }


    template<typename T=U, size_t ndim>
    FASTOR_INLINE
    std::tuple<Tensor<T,ndim>,Tensor<T,ndim,ndim>, typename ElectroMechanicsHessianType<T,ndim>::return_type>
    _KineticMeasures_(const T *Fnp, const T *Enp) {


        // CREATE FASTOR TENSORS
        Tensor<T,ndim,ndim> F;
        Tensor<T,ndim> E;
        // COPY NUMPY ARRAY TO FASTOR TENSORS
        copy_numpy(F,Fnp);
        copy_numpy(E,Enp);

        // FIND THE KINEMATIC MEASURES
        Tensor<T,ndim,ndim> I; I.eye2();
        auto J = determinant(F);
        // auto H = cofactor(F);
        auto b = matmul(F,transpose(F));

        // COMPUTE ELECTRIC DISPLACEMENT
        auto legendre_transform = _LegendreTransform_<T>();
        auto D = legendre_transform.QuadratureNewtonRaphson(*this,F,E);

        auto innerDD = inner(D,D);
        auto outerDD = outer(D,D);

        // COMPUTE CAUCHY STRESS TENSOR
        T trb = trace(b);
        if (ndim == 2) {
            trb += 1.;
        }

        auto coeff = J*J*J/mue/(eps_e*eps_e);

        Tensor<T,ndim,ndim> sigma_mech = 2.*mu1/J*b + \
            2.*mu2/J*(trb*b - matmul(b,b)) - \
            2.*(mu1+2*mu2+6*mue)/J*I + \
            lamb*(J-1)*I + \
            4.*mue/J*trb*b;

        Tensor<T,ndim,ndim> sigma_electric = 1./eps_2*(outerDD - 0.5*innerDD*I);

        Tensor<T,ndim,ndim> simga_reg = 4.*J/eps_e*(innerDD*b + trb*outerDD) + \
            4.0*coeff*innerDD*outerDD;

        Tensor<T,ndim,ndim> sigma = sigma_mech + sigma_electric + simga_reg;

        // FIND ELASTICITY TENSOR
        // auto II_ijkl = einsum<Index<i,j>,Index<k,l>>(I,I);
        auto II_ijkl = outer(I,I);
        auto II_ikjl = permutation<Index<i,k,j,l>>(II_ijkl);
        auto II_iljk = permutation<Index<i,l,j,k>>(II_ijkl);

        // auto bb_ijkl = einsum<Index<i,j>,Index<k,l>>(b,b);
        auto bb_ijkl = outer(b,b);
        auto bb_ikjl = permutation<Index<i,k,j,l>>(bb_ijkl);
        auto bb_iljk = permutation<Index<i,l,j,k>>(bb_ijkl);

        // auto IDD_ijkl = einsum<Index<i,j>,Index<k,l>>(I,outerDD);
        // auto DDI_ijkl = einsum<Index<i,j>,Index<k,l>>(outerDD,I);
        auto IDD_ijkl = outer(I,outerDD);
        auto DDI_ijkl = outer(outerDD,I);

        // auto bDD_ijkl = einsum<Index<i,j>,Index<k,l>>(b,outerDD);
        // auto DDb_ijkl = einsum<Index<i,j>,Index<k,l>>(outerDD,b);
        // auto DDDD_ijkl = einsum<Index<i,j>,Index<k,l>>(outerDD,outerDD);
        auto bDD_ijkl = outer(b,outerDD);
        auto DDb_ijkl = outer(outerDD,b);
        auto DDDD_ijkl = outer(outerDD,outerDD);

        Tensor<T,ndim,ndim,ndim,ndim> C_mech = 2.0*mu2/J*(2.0*bb_ijkl - bb_ikjl - bb_iljk) + \
            (2.*(mu1+2*mu2+6*mue)/J - lamb*(J-1.) ) * (II_ikjl + II_iljk) + lamb*(2.*J-1.)*II_ijkl + \
            8.*mue/J*bb_ijkl;

        Tensor<T,ndim,ndim,ndim,ndim> C_elect = 1./eps_2*(0.5*innerDD*( II_ijkl + II_ikjl + II_iljk) - \
                    IDD_ijkl - DDI_ijkl );

        Tensor<T,ndim,ndim,ndim,ndim> C_reg = 8.*J/eps_e*( bDD_ijkl + DDb_ijkl ) + \
            8.*coeff*DDDD_ijkl;

        Tensor<T,ndim,ndim,ndim,ndim> elasticity = C_mech + C_elect + C_reg;

        // FIND COUPLING TENSOR
        auto ID_ijk = einsum<Index<i,j>,Index<k>>(I,D);
        auto ID_ikj = permutation<Index<i,k,j>>(ID_ijk);
        auto ID_jki = permutation<Index<j,k,i>>(ID_ijk);

        // auto bD_ijk = einsum<Index<i,j>,Index<k>>(b,D);
        auto bD_ijk = outer(b,D);
        // auto bD_ikj = permutation<Index<i,k,j>>(bD_ijk);
        // auto bD_jki = permutation<Index<j,k,i>>(bD_ijk);

        auto DDD_ijk = outer(D,outerDD);

        Tensor<T,ndim,ndim,ndim> coupling =  1./eps_2*(ID_ikj + ID_jki - ID_ijk) + \
            8*J/eps_e*bD_ijk + 4*J/eps_e*trb*( ID_ikj + ID_jki ) + \
            4.*coeff*innerDD* ( ID_ikj + ID_jki ) + 8.*coeff*DDD_ijk;

        // FIND DIELELCTRIC TENSOR
        Tensor<T,ndim,ndim> dielectric = J/eps_1*inverse(b)  + 1./eps_2*I + 4.*J/eps_e*trb*I + \
            8.*coeff*(outerDD + 0.5*innerDD*I);

        // PERFORM LEGENDRE TRANSFORM
        auto hessian = legendre_transform.InternalEnergyToEnthalpy(elasticity,coupling,dielectric);

        auto kinetics = std::make_tuple(D,sigma,hessian);
        return kinetics;
    }

    template<typename T, size_t N>
    Tensor<T,N,N> DielectricTensor(const Tensor<T,N,N> &F, const Tensor<T,N> &D) const {

        Tensor<Real,N,N> I; I.eye();
        auto J = determinant(F);
        auto b = matmul(F,transpose(F));
        auto coeff = J*J*J/mue/(eps_e*eps_e);

        auto innerDD = inner(D,D);
        auto outerDD = outer(D,D);

        // COMPUTE CAUCHY STRESS TENSOR
        T trb = trace(b);
        if (N == 2) {
            trb += 1.;
        }

        Tensor<T,N,N> dielectric = J/eps_1*inverse(b)  + 1./eps_2*I + 4.*J/eps_e*trb*I + \
            8.*coeff*(outerDD + 0.5*innerDD*I);

        return dielectric;
    }

    template<typename T>
    void KineticMeasures(T* Dnp, T *Snp, T* Hnp, int ndim, int ngauss, const T *Fnp, const T *Enp);


};

template<> template<>
void _IsotropicElectroMechanics_107_<Real>::KineticMeasures<Real>(Real *Dnp, Real *Snp, Real* Hnp,
    int ndim, int ngauss, const Real *Fnp, const Real *Enp) {

    if (ndim==3) {
        Tensor<Real,3> D;
        Tensor<Real,3,3> stress;
        Tensor<Real,9,9> hessian;
        for (int g=0; g<ngauss; ++g) {
            std::tie(D,stress,hessian) =_KineticMeasures_<Real,3>(Fnp+9*g, Enp+3*g);
            copy_fastor(Dnp,D,g*3);
            copy_fastor(Snp,stress,g*9);
            copy_fastor(Hnp,hessian,g*81);
        }
    }
    else if (ndim==2) {
        Tensor<Real,2> D;
        Tensor<Real,2,2> stress;
        Tensor<Real,5,5> hessian;
        for (int g=0; g<ngauss; ++g) {
            std::tie(D,stress,hessian) =_KineticMeasures_<Real,2>(Fnp+4*g, Enp+2*g);
            copy_fastor(Dnp,D,g*2);
            copy_fastor(Snp,stress,g*4);
            copy_fastor(Hnp,hessian,g*25);
        }
    }
}
