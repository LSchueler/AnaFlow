# -*- coding: utf-8 -*-
"""
=======================================================
Groundwater flow solutions (:mod:`anaflow.gwsolutions`)
=======================================================

.. currentmodule:: anaflow.gwsolutions

Anaflow subpackage providing solutions for the groundwater flow equation.

Functions
---------
The following functions are provided

.. autosummary::
   :toctree: generated/

   thiem - Thiem solution for steady state pumping
   theis - Theis solution for transient pumping
   ext_thiem2D - extended Thiem solution in 2D
   ext_theis2D - extended Theis solution in 2D
   ext_thiem3D - extended Thiem solution in 3D
   ext_theis3D - extended Theis solution in 3D
   diskmodel - Solution for a diskmodel
   lap_transgwflow_cyl - Solution for a diskmodel in laplace inversion

"""

from __future__ import absolute_import, division, print_function

import warnings

import numpy as np
import scipy.sparse as sps
from scipy.special import i0, i1, k0, k1, exp1, expi

from anaflow.laplace import stehfest as sf
from anaflow.helper import well_solution, aniso, radii,\
                           T_CG, T_CG_error,\
                           K_CG, K_CG_error

__all__ = ["thiem", "theis",
           "ext_thiem2D", "ext_theis2D",
           "ext_thiem3D", "ext_theis3D",
           "diskmodel", "lap_transgwflow_cyl"]


###############################################################################
# Thiem-solution
###############################################################################

def thiem(rad, Rref,
          T, Qw,
          href=0.0):
    '''
    The Thiem solution for steady-state flow under a pumping condition
    in a confined and homogeneous aquifer.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    Rref : float
        Reference radius with known head (see href)
    T : float
        Given transmissivity of the aquifer
    Qw : float
        Pumpingrate at the well
    href : float, optional
        Reference head at the reference-radius "Rref". Default: 0.0

    Returns
    -------
    thiem : ndarray
        Array with all heads at the given radii.

    Notes
    -----
    The parameters "rad", "Rref" and "T" will be checked for positivity.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> thiem([1,2,3], 10, 0.001, -0.001)
    array([-0.3664678 , -0.25615   , -0.19161822])
    '''

    rad = np.squeeze(rad)

    # check the input
    if Rref <= 0.0:
        raise ValueError(
            "The reference-radius needs to be greater than 0")
    if np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if T <= 0.0:
        raise ValueError(
            "The Transmissivity needs to be positiv")

    return -Qw/(2.0*np.pi*T)*np.log(rad/Rref) + href


###############################################################################
# 2D version of extended Theis
###############################################################################

def ext_thiem2D(rad, Rref,
                TG, sig2, corr, Qw,
                href=0.0, Twell=None, prop=1.6):
    '''
    The extended Thiem solution for steady-state flow under
    a pumping condition in a confined aquifer.
    The type curve is describing the effective drawdown
    in a 2D statistical framework, where the transmissivity distribution is
    following a log-normal distribution with a gaussian correlation function.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    Rref : float
        Reference radius with known head (see href)
    TG : float
        Geometric-mean transmissivity-distribution
    sig2 : float
        log-normal-variance of the transmissivity-distribution
    corr : float
        corralation-length of transmissivity-distribution
    Qw : float
        Pumpingrate at the well
    href : float, optional
        Reference head at the reference-radius "Rref". Default: 0.0
    Twell : float, optional
        Explicit transmissivity value at the well. Default: None
    prop: float, optional
        Proportionality factor used within the upscaling procedure.
        Default: 1.6

    Returns
    -------
    ext_thiem2D : ndarray
        Array with all heads at the given radii.

    Notes
    -----
    The parameters "rad", "Rref", "TG", "sig2", "corr", "Twell" and "prop"
    will be checked for positivity.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> ext_thiem2D([1,2,3], 10, 0.001, 1, 10, -0.001)
    array([-0.53084596, -0.35363029, -0.25419375])
    '''

    rad = np.squeeze(rad)

    # check the input
    if Rref <= 0.0:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if TG <= 0.0:
        raise ValueError(
            "The Transmissivity needs to be positiv")
    if Twell is not None and Twell <= 0.0:
        raise ValueError(
            "The Transmissivity at the well needs to be positiv")
    if sig2 <= 0.0:
        raise ValueError(
            "The variance needs to be positiv")
    if corr <= 0.0:
        raise ValueError(
            "The correlationlength needs to be positiv")
    if prop <= 0.0:
        raise ValueError(
            "The proportionalityfactor needs to be positiv")

    # define some substitions to shorten the result
    if Twell is not None:
        chi = np.log(Twell) - np.log(TG)
    else:
        chi = -sig2/2.0

    Q = -Qw/(4.0*np.pi*TG)
    C = (prop/corr)**2

    # derive the result
    res = -expi(-chi/(1.+C*rad**2))
    res -= np.exp(-chi)*exp1(chi/(1.+C*rad**2) - chi)
    res += expi(-chi/(1.+C*Rref**2))
    res += np.exp(-chi)*exp1(chi/(1.+C*Rref**2) - chi)
    res *= Q
    res += href

    return res


###############################################################################
# 3D version of extended Theis
###############################################################################

def ext_thiem3D(rad, Rref,
                KG, sig2, corr, e, Qw, L,
                href=0.0, Kwell="KH", prop=1.6):
    '''
    The extended Thiem solution for steady-state flow under
    a pumping condition in a confined aquifer.
    The type curve is describing the effective drawdown
    in a 3D statistical framework, where the conductivity distribution is
    following a log-normal distribution with a gaussian correlation function
    and taking vertical anisotropy into account.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    Rref : float
        Reference radius with known head (see href)
    KG : float
        Geometric-mean conductivity-distribution
    sig2 : float
        log-normal-variance of the conductivity-distribution
    corr : float
        corralation-length of conductivity-distribution
    e : float
        Anisotropy-ratio of the vertical and horizontal corralation-lengths
    Qw : float
        Pumpingrate at the well
    L : float
        Thickness of the aquifer
    href : float, optional
        Reference head at the reference-radius "Rref". Default: 0.0
    Kwell : string/float, optional
        Explicit conductivity value at the well. One can choose between the
        harmonic mean ("KH"), the arithmetic mean ("KA") or an arbitrary float
        value. Default: "KH"
    prop: float, optional
        Proportionality factor used within the upscaling procedure.
        Default: 1.6

    Returns
    -------
    ext_thiem3D : ndarray
        Array with all heads at the given radii.

    Notes
    -----
    The parameters "rad", "Rref", "KG", "sig2", "corr", "Kwell" and "prop"
    will be checked for positivity. The anisotropy factor must be greater 0
    and less or equal 1.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> ext_thiem3D([1,2,3], 10, 0.001, 1, 10, 1, -0.001, 1)
    array([-0.48828026, -0.31472059, -0.22043022])
    '''

    rad = np.squeeze(rad)

    # check the input
    if Rref <= 0.0:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if Kwell != "KA" and Kwell != "KH" and not isinstance(Kwell, float):
        raise ValueError(
            "The well-conductivity should be given as float or 'KA' resp 'KH'")
    if isinstance(Kwell, float) and Kwell <= 0.:
        raise ValueError(
            "The well-conductivity needs to be positiv")
    if KG <= 0.0:
        raise ValueError(
            "The Transmissivity needs to be positiv")
    if sig2 <= 0.0:
        raise ValueError(
            "The variance needs to be positiv")
    if corr <= 0.0:
        raise ValueError(
            "The correlationlength needs to be positiv")
    if L <= 0.0:
        raise ValueError(
            "The aquifer-thickness needs to be positiv")
    if not 0.0 < e <= 1.0:
        raise ValueError(
            "The anisotropy-ratio must be > 0 and <= 1")
    if prop <= 0.0:
        raise ValueError(
            "The proportionalityfactor needs to be positiv")

    # define some substitions to shorten the result
    Kefu = KG*np.exp(sig2*(0.5 - aniso(e)))
    if Kwell == "KH":
        chi = sig2*(aniso(e)-1.)
    elif Kwell == "KA":
        chi = sig2*aniso(e)
    else:
        chi = np.log(Kwell) - np.log(Kefu)

    Q = -Qw/(2.0*np.pi*Kefu)
    C = (prop/corr/e**(1./3.))**2

    sub11 = np.sqrt(1. + C*Rref**2)
    sub12 = np.sqrt(1. + C*rad**2)

    sub21 = np.log(sub12 + 1.) - np.log(sub11 + 1.)
    sub21 -= 1.0/sub12 - 1.0/sub11

    sub22 = np.log(sub12) - np.log(sub11)
    sub22 -= 0.50/sub12**2 - 0.50/sub11**2
    sub22 -= 0.25/sub12**4 - 0.25/sub11**4

    # derive the result
    res = np.exp(-chi)*(np.log(rad) - np.log(Rref))
    res += sub21*np.sinh(chi) + sub22*(1. - np.cosh(chi))
    res *= Q
    res += href

    return res


###############################################################################
# Theis-solution
###############################################################################

def theis(rad, time,
          T, S, Qw,
          struc_grid=True, rwell=0.0, rinf=np.inf, hinf=0.0,
          stehfestn=12):
    '''
    The Theis solution for transient flow under a pumping condition
    in a confined and homogeneous aquifer.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    time : ndarray
        Array with all time-points where the function should be evaluated
    T : float
        Given transmissivity of the aquifer
    S : float
        Given storativity of the aquifer
    Qw : float
        Pumpingrate at the well
    struc_grid : bool, optional
        If this is set to "False", the "rad" and "time" array will be merged
        and interpreted as single, r-t points. In this case they need to have
        the same shapes. Otherwise a structured r-t grid is created.
        Default: True
    rwell : float, optional
        Inner radius of the pumping-well. Default: 0.0
    rinf : float, optional
        Radius of the outer boundary of the aquifer. Default: inf
    hinf : float, optional
        Reference head at the outer boundary "rinf". Default: 0.0
    stehfestn : int, optional
        If "rwell" or "rinf" are not default, the solution is calculated in
        Laplace-space. The back-transformation is performed with the stehfest-
        algorithm. Here you can specify the number of interations within this
        algorithm. Default: 12

    Returns
    -------
    theis : ndarray
        Array with all heads at the given radii and time-points.

    Notes
    -----
    The parameters "rad", "Rref" and "T" will be checked for positivity.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> theis([1,2,3], [10,100], 0.001, 0.001, -0.001)
    array([[-0.24959541, -0.14506368, -0.08971485],
           [-0.43105106, -0.32132823, -0.25778313]])
    '''

    # ensure that 'rad' and 'time' are arrays
    rad = np.squeeze(rad)
    time = np.array(time).reshape(-1)

    if not struc_grid:
        grid_shape = rad.shape
        rad = rad.reshape(-1)

    # check the input
    if rwell < 0.0:
        raise ValueError(
            "The wellradius needs to be >= 0")
    if rinf <= rwell:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if np.any(rad < rwell) or np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if np.any(time <= 0.0):
        raise ValueError(
            "The given times need to be > 0")
    if not struc_grid and not rad.shape == time.shape:
        raise ValueError(
            "For unstructured grid the number of time- & radii-pts must equal")
    if T <= 0.0:
        raise ValueError(
            "The Transmissivity needs to be positiv")
    if S <= 0.0:
        raise ValueError(
            "The Storage needs to be positiv")
    if not isinstance(stehfestn, int):
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be an integer")
    if stehfestn <= 1:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be > 1")
    if stehfestn % 2 != 0:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be even")

    if rwell == 0.0 and rinf == np.inf:
        res = well_solution(rad, time, T, S, Qw)

    else:
        rpart = np.array([rwell, rinf])
        Tpart = np.array([T])
        Spart = np.array([S])

        # write the paramters in kwargs to use the stehfest-algorithm
        kwargs = {"rad": rad,
                  "Qw": Qw,
                  "rpart": rpart,
                  "Spart": Spart,
                  "Tpart": Tpart}

        # call the stehfest-algorithm
        res = sf(lap_transgwflow_cyl, time, bound=stehfestn, kwargs=kwargs)

    # if the input are unstructured space-time points, return an array
    if not struc_grid and len(grid_shape) > 0:
        res = np.copy(np.diag(res).reshape(grid_shape))

    # add the reference head
    res += hinf

    return res


###############################################################################
# 2D version of extended Theis
###############################################################################

def ext_theis2D(rad, time,
                TG, sig2, corr, S, Qw,
                struc_grid=True,
                rwell=0.0, rinf=np.inf, hinf=0.0,
                Twell=None, T_err=0.01,
                prop=1.6, stehfestn=12, parts=30):
    '''
    The extended Theis solution for transient flow under
    a pumping condition in a confined aquifer.
    The type curve is describing the effective drawdown
    in a 2D statistical framework, where the transmissivity distribution is
    following a log-normal distribution with a gaussian correlation function.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    time : ndarray
        Array with all time-points where the function should be evaluated
    TG : float
        Geometric-mean transmissivity-distribution
    sig2 : float
        log-normal-variance of the transmissivity-distribution
    corr : float
        corralation-length of transmissivity-distribution
    S : float
        Given storativity of the aquifer
    Qw : float
        Pumpingrate at the well
    struc_grid : bool, optional
        If this is set to "False", the "rad" and "time" array will be merged
        and interpreted as single, r-t points. In this case they need to have
        the same shapes. Otherwise a structured r-t grid is created.
        Default: True
    rwell : float, optional
        Inner radius of the pumping-well. Default: 0.0
    rinf : float, optional
        Radius of the outer boundary of the aquifer. Default: inf
    hinf : float, optional
        Reference head at the outer boundary "rinf". Default: 0.0
    Twell : float, optional
        Explicit transmissivity value at the well. Default: None
    T_err : float, optional
        Absolute error for the farfield transmissivity for calculating the
        cutoff-point of the solution. Default: 0.01
    prop: float, optional
        Proportionality factor used within the upscaling procedure.
        Default: 1.6
    stehfestn : int, optional
        Since the solution is calculated in Laplace-space, the
        back-transformation is performed with the stehfest-algorithm.
        Here you can specify the number of interations within this
        algorithm. Default: 12
    parts : int, optional
        Since the solution is calculated by setting the transmissity to local
        constant values, one needs to specify the number of partitions of the
        transmissivity. Default: 30

    Returns
    -------
    ext_theis2D : ndarray
        Array with all heads at the given radii and time-points.

    Notes
    -----
    The parameters "rad", "Rref", "TG", "sig2", "corr", "S", "Twell" and "prop"
    will be checked for positivity.
    "T_err" must be greater 0 and less or equal 1.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> ext_theis2D([1,2,3], [10,100], 0.001, 1, 10, 0.001, -0.001)
    array([[-0.3381231 , -0.17430066, -0.09492601],
           [-0.58557452, -0.40907021, -0.31112835]])
    '''

    # ensure that 'rad' and 'time' are arrays
    rad = np.squeeze(rad)
    time = np.array(time).reshape(-1)

    if not struc_grid:
        grid_shape = rad.shape
        rad = rad.reshape(-1)

    # check the input
    if rwell < 0.0:
        raise ValueError(
            "The wellradius needs to be >= 0")
    if rinf <= rwell:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if np.any(rad < rwell) or np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if np.any(time <= 0.0):
        raise ValueError(
            "The given times need to be >= 0")
    if not struc_grid and not rad.shape == time.shape:
        raise ValueError(
            "For unstructured grid the number of time- & radii-pts must equal")
    if TG <= 0.0:
        raise ValueError(
            "The Transmissivity needs to be positiv")
    if Twell is not None and Twell <= 0.0:
        raise ValueError(
            "The Transmissivity at the well needs to be positiv")
    if sig2 <= 0.0:
        raise ValueError(
            "The variance needs to be positiv")
    if corr <= 0.0:
        raise ValueError(
            "The correlationlength needs to be positiv")
    if S <= 0.0:
        raise ValueError(
            "The Storage needs to be positiv")
    if prop <= 0.0:
        raise ValueError(
            "The proportionalityfactor needs to be positiv")
    if not isinstance(stehfestn, int):
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be an integer")
    if stehfestn <= 1:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be > 1")
    if stehfestn % 2 != 0:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be even")
    if not isinstance(parts, int):
        raise ValueError(
            "The numbor of partitions needs to be an integer")
    if parts <= 1:
        raise ValueError(
            "The numbor of partitions needs to be at least 2")
    if not 0.0 < T_err < 1.0:
        raise ValueError(
            "The relative error of Transmissivity needs to be within (0,1)")

    # genearte rlast from a given relativ-error to farfield-transmissivity
    rlast = T_CG_error(T_err, TG, sig2, corr, prop, Twell=Twell)

    # generate the partition points and the evaluation-points of transmissivity
    rpart, fpart = radii(parts, rwell=rwell, rinf=rinf, rlast=rlast)

    # calculate the transmissivity values within each partition
    Tpart = T_CG(fpart, TG, sig2, corr, prop, Twell=Twell)

    # write the paramters in kwargs to use the stehfest-algorithm
    kwargs = {"rad": rad,
              "Qw": Qw,
              "rpart": rpart,
              "Spart": S*np.ones(parts),
              "Tpart": Tpart}

    # call the stehfest-algorithm
    res = sf(lap_transgwflow_cyl, time, bound=stehfestn, kwargs=kwargs)

    # if the input are unstructured space-time points, return an array
    if not struc_grid and len(grid_shape) > 0:
        res = np.copy(np.diag(res).reshape(grid_shape))

    # add the reference head
    res += hinf

    return res


###############################################################################
# 3D version of extended Theis
###############################################################################

def ext_theis3D(rad, time,
                KG, sig2, corr, e, S, Qw, L,
                struc_grid=True,
                rwell=0.0, rinf=np.inf, hinf=0.0,
                Kwell="KH", K_err=0.01,
                prop=1.6, stehfestn=12, parts=30):
    '''
    The extended Theis solution for transient flow under
    a pumping condition in a confined aquifer.
    The type curve is describing the effective drawdown
    in a 3D statistical framework, where the transmissivity distribution is
    following a log-normal distribution with a gaussian correlation function
    and taking vertical anisotropy into account.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    time : ndarray
        Array with all time-points where the function should be evaluated
    KG : float
        Geometric-mean conductivity-distribution
    sig2 : float
        log-normal-variance of the conductivity-distribution
    corr : float
        corralation-length of conductivity-distribution
    e : float
        Anisotropy-ratio of the vertical and horizontal corralation-lengths
    S : float
        Given storativity of the aquifer
    Qw : float
        Pumpingrate at the well
    L : float
        Thickness of the aquifer
    struc_grid : bool, optional
        If this is set to "False", the "rad" and "time" array will be merged
        and interpreted as single, r-t points. In this case they need to have
        the same shapes. Otherwise a structured r-t grid is created.
        Default: True
    rwell : float, optional
        Inner radius of the pumping-well. Default: 0.0
    rinf : float, optional
        Radius of the outer boundary of the aquifer. Default: inf
    hinf : float, optional
        Reference head at the outer boundary "rinf". Default: 0.0
    Kwell : string/float, optional
        Explicit conductivity value at the well. One can choose between the
        harmonic mean ("KH"), the arithmetic mean ("KA") or an arbitrary float
        value. Default: "KH"
    K_err : float, optional
        Absolute error for the farfield conductivity for calculating the
        cutoff-point of the solution. Default: 0.01
    prop: float, optional
        Proportionality factor used within the upscaling procedure.
        Default: 1.6
    stehfestn : int, optional
        Since the solution is calculated in Laplace-space, the
        back-transformation is performed with the stehfest-algorithm.
        Here you can specify the number of interations within this
        algorithm. Default: 12
    parts : int, optional
        Since the solution is calculated by setting the transmissity to local
        constant values, one needs to specify the number of partitions of the
        transmissivity. Default: 30

    Returns
    -------
    ext_theis3D : ndarray
        Array with all heads at the given radii and time-points.

    Notes
    -----
    The parameters "rad", "Rref", "KG", "sig2", "corr", "S", "Twell" and "prop"
    will be checked for positivity.
    The Anisotropy-ratio "e" must be greater 0 and less or equal 1.
    "T_err" must be greater 0 and less or equal 1.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> ext_theis3D([1,2,3], [10,100], 0.001, 1, 10, 1, 0.001, -0.001, 1)
    array([[-0.32845576, -0.16741654, -0.09134294],
           [-0.54238241, -0.36982686, -0.27754856]])
    '''

    # ensure that 'rad' and 'time' are arrays
    rad = np.squeeze(rad)
    time = np.array(time).reshape(-1)

    if not struc_grid:
        grid_shape = rad.shape
        rad = rad.reshape(-1)

    # check the input
    if rwell < 0.0:
        raise ValueError(
            "The wellradius needs to be >= 0")
    if rinf <= rwell:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if np.any(rad < rwell) or np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if np.any(time <= 0.0):
        raise ValueError(
            "The given times need to be >= 0")
    if not struc_grid and not rad.shape == time.shape:
        raise ValueError(
            "For unstructured grid the number of time- & radii-pts must equal")
    if Kwell != "KA" and Kwell != "KH" and not isinstance(Kwell, float):
        raise ValueError(
            "The well-conductivity should be given as float or 'KA' resp 'KH'")
    if isinstance(Kwell, float) and Kwell <= 0.:
        raise ValueError(
            "The well-conductivity needs to be positiv")
    if KG <= 0.0:
        raise ValueError(
            "The conductivity needs to be positiv")
    if sig2 <= 0.0:
        raise ValueError(
            "The variance needs to be positiv")
    if corr <= 0.0:
        raise ValueError(
            "The correlationlength needs to be positiv")
    if S <= 0.0:
        raise ValueError(
            "The Storage needs to be positiv")
    if L <= 0.0:
        raise ValueError(
            "The aquifer-thickness needs to be positiv")
    if prop <= 0.0:
        raise ValueError(
            "The proportionalityfactor needs to be positiv")
    if not isinstance(stehfestn, int):
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be an integer")
    if stehfestn <= 1:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be > 1")
    if stehfestn % 2 != 0:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be even")
    if not isinstance(parts, int):
        raise ValueError(
            "The numbor of partitions needs to be an integer")
    if parts <= 1:
        raise ValueError(
            "The numbor of partitions needs to be at least 2")
    if not 0.0 < K_err < 1.0:
        raise ValueError(
            "The relative error of Transmissivity needs to be within (0,1)")

    # genearte rlast from a given relativ-error to farfield-transmissivity
    rlast = K_CG_error(K_err, KG, sig2, corr, e, prop, Kwell=Kwell)

    # generate the partition points and the evaluation-points of transmissivity
    rpart, fpart = radii(parts, rwell=rwell, rinf=rinf, rlast=rlast)

    # calculate the transmissivity values within each partition
    Tpart = K_CG(fpart, KG, sig2, corr, e, prop, Kwell=Kwell)

    # write the paramters in kwargs to use the stehfest-algorithm
    kwargs = {"rad": rad,
              "Qw": Qw/L,
              "rpart": rpart,
              "Spart": S*np.ones(parts),
              "Tpart": Tpart}

    # call the stehfest-algorithm
    res = sf(lap_transgwflow_cyl, time, bound=stehfestn, kwargs=kwargs)

    # if the input are unstructured space-time points, return an array
    if not struc_grid and len(grid_shape) > 0:
        res = np.copy(np.diag(res).reshape(grid_shape))

    # add the reference head
    res += hinf

    return res


###############################################################################
# solution for a disk-model
###############################################################################

def diskmodel(rad, time,
              Tpart, Spart, Rpart, Qw,
              struc_grid=True, rwell=0.0, rinf=np.inf, hinf=0.0,
              stehfestn=12):
    '''
    A diskmodel for transient flow under a pumping condition
    in a confined aquifer. The solutions assumes concentric disks around the
    pumpingwell, where each disk has its own transmissivity and storativity
    value.

    Parameters
    ----------
    rad : ndarray
        Array with all radii where the function should be evaluated
    time : ndarray
        Array with all time-points where the function should be evaluated
    Tpart : ndarray
        Given transmissivity values for each disk
    Spart : ndarray
        Given storativity values for each disk
    Rpart : ndarray
        Given radii separating the disks
    Qw : float
        Pumpingrate at the well
    struc_grid : bool, optional
        If this is set to "False", the "rad" and "time" array will be merged
        and interpreted as single, r-t points. In this case they need to have
        the same shapes. Otherwise a structured r-t grid is created.
        Default: True
    rwell : float, optional
        Inner radius of the pumping-well. Default: 0.0
    rinf : float, optional
        Radius of the outer boundary of the aquifer. Default: inf
    hinf : float, optional
        Reference head at the outer boundary "rinf". Default: 0.0
    stehfestn : int, optional
        Since the solution is calculated in Laplace-space, the
        back-transformation is performed with the stehfest-algorithm.
        Here you can specify the number of interations within this
        algorithm. Default: 12

    Returns
    -------
    diskmodel : ndarray
        Array with all heads at the given radii and time-points.

    Notes
    -----
    The parameters "rad", "time", "Tpart" and "Spart" will be checked for
    positivity.
    If you want to use cartesian coordiantes, just use the formula
    r = sqrt(x**2 + y**2)

    Example
    -------
    >>> diskmodel([1,2,3], [10, 100], [1e-3, 2e-3], [1e-3, 1e-3], [2], -1e-3)
    array([[-0.20312814, -0.09605675, -0.06636862],
           [-0.29785979, -0.18784251, -0.15582597]])
    '''

    # ensure that input is treated as arrays
    rad = np.squeeze(rad)
    time = np.array(time).reshape(-1)
    Tpart = np.array(Tpart)
    Spart = np.array(Spart)
    Rpart = np.array(Rpart)

    if not struc_grid:
        grid_shape = rad.shape
        rad = rad.reshape(-1)

    # check the input
    if rwell < 0.0:
        raise ValueError(
            "The wellradius needs to be >= 0")
    if rinf <= rwell:
        raise ValueError(
            "The upper boundary needs to be greater than the wellradius")
    if not all(Rpart[i] < Rpart[i+1] for i in range(len(Rpart)-1)):
        raise ValueError(
            "The radii of the zones need to be sorted")
    if np.any(Rpart <= rwell):
        raise ValueError(
            "The radii of the zones need to be greater than the wellradius")
    if np.any(Rpart >= rinf):
        raise ValueError(
            "The radii of the zones need to be less than the outer radius")
    if np.any(rad < rwell) or np.any(rad <= 0.0):
        raise ValueError(
            "The given radii need to be greater than the wellradius")
    if np.any(time <= 0.0):
        raise ValueError(
            "The given times need to be >= 0")
    if not struc_grid and not rad.shape == time.shape:
        raise ValueError(
            "For unstructured grid the number of time- & radii-pts must equal")
    if np.any(Tpart <= 0.0):
        raise ValueError(
            "The Transmissivities need to be positiv")
    if np.any(Spart <= 0.0):
        raise ValueError(
            "The Storages need to be positiv")
    if not isinstance(stehfestn, int):
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be an integer")
    if stehfestn <= 1:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be > 1")
    if stehfestn % 2 != 0:
        raise ValueError(
            "The boundary for the Stehfest-algorithm needs to be even")

    rpart = np.append(np.array([rwell]), Rpart)
    rpart = np.append(rpart, np.array([rinf]))

    # write the paramters in kwargs to use the stehfest-algorithm
    kwargs = {"rad": rad,
              "Qw": Qw,
              "rpart": rpart,
              "Spart": Spart,
              "Tpart": Tpart}

    # call the stehfest-algorithm
    res = sf(lap_transgwflow_cyl, time, bound=stehfestn, kwargs=kwargs)

    # if the input are unstructured space-time points, return an array
    if not struc_grid and len(grid_shape) > 0:
        res = np.copy(np.diag(res).reshape(grid_shape))

    # add the reference head
    res += hinf

    return res


###############################################################################
# The generic solver of the 2D radial transient groundwaterflow equation
# in Laplace-space with a pumping condition and a fix zero boundary-head
###############################################################################

def lap_transgwflow_cyl(s,
                        rad=None, rpart=None, Spart=None, Tpart=None, Qw=None):
    '''
    The solution of the diskmodel for transient flow under a pumping condition
    in a confined aquifer in Laplace-space.
    The solutions assumes concentric disks around the pumpingwell,
    where each disk has its own transmissivity and storativity value.

    Parameters
    ----------
    s : ndarray
        Array with all Laplace-space-points
        where the function should be evaluated
    rad : ndarray
        Array with all radii where the function should be evaluated
    Tpart : ndarray
        Given transmissivity values for each disk
    Spart : ndarray
        Given storativity values for each disk
    rpart : ndarray
        Given radii separating the disks as well as starting- and endpoints
    Qw : float
        Pumpingrate at the well

    Returns
    -------
    lap_transgwflow_cyl : ndarray
        Array with all values in laplace-space

    Example
    -------
    >>> lap_transgwflow_cyl([5,10],[1,2,3],[0,2,10],[1e-3,1e-3],[1e-3,2e-3],-1)
    array([[ -2.71359196e+00,  -1.66671965e-01,  -2.82986917e-02],
           [ -4.58447458e-01,  -1.12056319e-02,  -9.85673855e-04]])
    '''

    # ensure that input is treated as arrays
    s = np.squeeze(s)
    rad = np.squeeze(rad)
    rpart = np.squeeze(rpart)
    Spart = np.squeeze(Spart)
    Tpart = np.squeeze(Tpart)

    # get the number of partitions
    parts = len(Tpart)

    # initialize the result
    res = np.zeros(s.shape + rad.shape)

    # set the general pumping-condtion
    Q = Qw/(2.0*np.pi*Tpart[0])

    # if there is a homgeneouse aquifer, compute the result by hand
    if parts == 1:
        # calculate the square-root of the diffusivities
        difsr = np.sqrt(Spart[0]/Tpart[0])

        for si, se in np.ndenumerate(s):
            Cs = np.sqrt(se)*difsr

            # set the pumping-condition at the well
            Qs = Q/se

            # incorporate the boundary-conditions
            if rpart[0] == 0.0:
                Bs = Qs
                if rpart[-1] == np.inf:
                    As = 0.0
                else:
                    As = -Qs*k0(Cs*rpart[-1])/i0(Cs*rpart[-1])

            else:
                if rpart[-1] == np.inf:
                    As = 0.0
                    Bs = Qs/(Cs*rpart[0]*k1(Cs*rpart[0]))
                else:
                    det = i1(Cs*rpart[0])*k0(Cs*rpart[-1]) \
                        + k1(Cs*rpart[0])*i0(Cs*rpart[-1])
                    As = -Qs/(Cs*rpart[0])*k0(Cs*rpart[-1])/det
                    Bs = Qs/(Cs*rpart[0])*i0(Cs*rpart[-1])/det

            # calculate the head
            for ri, re in np.ndenumerate(rad):
                if re < rpart[-1]:
                    res[si+ri] = As*i0(Cs*re) + Bs*k0(Cs*re)

    # if there is more than one partition, create an equation system
    else:
        # initialize LHS and RHS for the linear equation system
        # Mb is the banded matrix for the Eq-System
        V = np.zeros(2*(parts))
        Mb = np.zeros((5, 2*(parts)))
        # the positions of the diagonals of the matrix set in Mb
        diagpos = [2, 1, 0, -1, -2]
        # set the standard boundary conditions for rwell=0.0 and rinf=np.inf
        Mb[1, 1] = 1.0
        Mb[-2, -2] = 1.0

        # calculate the consecutive fractions of the transmissivities
        Tfrac = Tpart[:-1]/Tpart[1:]

        # calculate the square-root of the diffusivities
        difsr = np.sqrt(Spart/Tpart)

        tmp = Tfrac*difsr[:-1]/difsr[1:]

        # iterate over the laplace-variable
        for si, se in np.ndenumerate(s):
            Cs = np.sqrt(se)*difsr

            # set the pumping-condition at the well
            # TODO: implement other pumping conditions
            V[0] = Q/se

            # set the boundary-conditions if needed
            if rpart[0] > 0.0:
                Mb[1, 1] = Cs[0]*rpart[0]*k1(Cs[0]*rpart[0])
                Mb[0, 2] = -Cs[0]*rpart[0]*i1(Cs[0]*rpart[0])
            if rpart[-1] < np.inf:
                Mb[-3, -1] = k0(Cs[-1]*rpart[-1])
                Mb[-2, -2] = i0(Cs[-1]*rpart[-1])

            # generate the equation system as banded matrix
            for i in range(parts-1):
                Mb[0, 2*i+3] = -k0(Cs[i+1]*rpart[i+1])
                Mb[1, 2*i+2:2*i+4] = [-i0(Cs[i+1]*rpart[i+1]),
                                      k1(Cs[i+1]*rpart[i+1])]
                Mb[2, 2*i+1:2*i+3] = [k0(Cs[i]*rpart[i+1]),
                                      -i1(Cs[i+1]*rpart[i+1])]
                Mb[3, 2*i:2*i+2] = [i0(Cs[i]*rpart[i+1]),
                                    -tmp[i]*k1(Cs[i]*rpart[i+1])]
                Mb[4, 2*i] = tmp[i]*i1(Cs[i]*rpart[i+1])

            # genearate the cooeficient matrix as a spare matrix
            M = sps.spdiags(Mb, diagpos, 2*parts, 2*parts, format="csc")

            # solve the Eq-Sys and ignore errors from the umf-pack
            with warnings.catch_warnings():
                # warnings.simplefilter("ignore")
                warnings.simplefilter("ignore", UserWarning)
                X = sps.linalg.spsolve(M, V, use_umfpack=True)

            # to suppress numerical errors, set NAN values to 0
            X[np.logical_not(np.isfinite(X))] = 0.0

            # calculate the head
            # look at: np.searchsorted
            #          np.unravel_index
            for ri, re in np.ndenumerate(rad):
                for i in range(parts):
                    if rpart[i] <= re < rpart[i+1]:
                        res[si+ri] = X[2*i]*i0(Cs[i]*re) \
                                   + X[2*i+1]*k0(Cs[i]*re)

        res[np.logical_not(np.isfinite(res))] = 0.0

    return res


if __name__ == "__main__":
    import doctest
    doctest.testmod()
