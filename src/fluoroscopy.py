
from numba import jit
import numpy as np
from math import fabs


@jit(nopython=True)
def core_convert2mumap(volRaw, HU_delta, mu_water_fluo, coef):
    nz, ny, nx = volRaw.shape
    phantom_mu = np.zeros((nz, ny, nx), "float32")

    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                # rescale
                HU = volRaw[iz, iy, ix] + HU_delta
                if HU <= 0.0:
                    phantom_mu[iz, iy, ix] = mu_water_fluo * (HU + 1000.0)/1000.0
                else:
                    phantom_mu[iz, iy, ix] = mu_water_fluo + HU * coef
                    
    return phantom_mu

@jit(nopython=True)
def core_convert2mumap_simple(volRaw, HU_delta, mu_water_fluo):
    nz, ny, nx = volRaw.shape
    phantom_mu = np.zeros((nz, ny, nx), "float32")

    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                # rescale
                HU = volRaw[iz, iy, ix] + HU_delta
                phantom_mu[iz, iy, ix] = mu_water_fluo * (HU + 1000.0)/1000.0
                      
    return phantom_mu

@jit(nopython=True)
def core_projection(image, phantom_mu, camNx, camNy, camSx, camSy, org_pos, 
                    RotX, RotZ, sysTranslation, pos_source, ctSize, ctSpacing):

    nz, ny, nx = phantom_mu.shape
    cur_pos_pix_x = org_pos[0]

    for y in range(camNy):   # camNy

        # Update ray pos
        cur_pos_pix_y = org_pos[1] - y*camSy 

        for x in range(camNx):    # camNx
            # Update ray pos
            cur_pos_pix_z = org_pos[2] + x*camSx

            mp1x = cur_pos_pix_x
            mp1y = RotX[1][1]*cur_pos_pix_y + RotX[1][2]*cur_pos_pix_z
            mp1z = RotX[2][1]*cur_pos_pix_y + RotX[2][2]*cur_pos_pix_z

            mp1x = RotZ[0][0]*mp1x + RotZ[0][1]*mp1y
            mp1y = RotZ[1][0]*mp1x + RotZ[1][1]*mp1y

            mp1x += sysTranslation[0]
            mp1y += sysTranslation[1]
            mp1z += sysTranslation[2]

            mp1x += (ctSize[0]*ctSpacing[0]*0.5)
            mp1y += (ctSize[1]*ctSpacing[1]*0.5)
            mp1z += (ctSize[2]*ctSpacing[2]*0.5)

            mp1x /= ctSpacing[0]
            mp1y /= ctSpacing[1]
            mp1z /= ctSpacing[2]

            ##### DDA #########################################################
            fdx = pos_source[0] - mp1x
            fdy = pos_source[1] - mp1y
            fdz = pos_source[2] - mp1z
            
            flx = fabs(fdx)
            fly = fabs(fdy)
            flz = fabs(fdz)
            ilength = int(fly)
            if flx > ilength:
                ilength = int(flx)
            if flz > ilength:
                ilength = int(flz)

            flength = 1.0 / float(ilength)
            fxinc = fdx * flength
            fyinc = fdy * flength
            fzinc = fdz * flength

            fx = mp1x
            fy = mp1y
            fz = mp1z

            val = 0.0

            for i in range(ilength):
                if (fx >= 0 and fy >= 0 and fz >= 0 and
                    fx < nx and fy < ny and fz < nz ):

                    ix = int(fx)
                    iy = int(fy)
                    iz = int(fz)

                    val += phantom_mu[iz, iy, ix]

                fx += fxinc
                fy += fyinc
                fz += fzinc
            ###################################################################

            image[y, x] = val

    return image


class fluoroscopy:
    """
    Fluoroscopy code translated from c from our old firework library
    """

    def __init__(self):
        # Translation
        self.sysTrans = np.matrix([[0],
                                   [0],
                                   [0]], 'float32')
        # Rotation around Z (LAO-RAO)
        self.sysRotZ = np.matrix([[1, 0, 0],
                                   [0, 1, 0],
                                   [0, 0, 1]], 'float32')

        # Rotation around X (CRA-CAU)
        self.sysRotX = np.matrix([[1, 0, 0],
                                   [0, 1, 0],
                                   [0, 0, 1]], 'float32')

    def setImage(self, aVolRaw, dVolHeader):
        self.volRaw = aVolRaw.copy()
        self.volHeader = dVolHeader.copy()
        
    def setPose(self, rotX, rotZ, trans):
        self.sysRotX = rotX.copy()
        self.sysRotZ = rotZ.copy()
        self.sysTrans = trans.copy()

    def setCamera(self, nx, ny, sx, sy, camDistIsocenter):
        self.camNx = nx
        self.camNy = ny
        self.camSx = sx
        self.camSy = sy
        self.camDistIso = camDistIsocenter

    def setSource(self, energy, srcDistIsocenter):
        self.srcEnergy = energy
        self.srcDistIso = srcDistIsocenter

    def computeMuMap(self):
        # convert phantom to the required energy
        ctEnergy = 0.06 # MeV TODO pick the value from MHD
        # self.phantom_mu = self.convert2mumap_simple(self.srcEnergy)
        self.phantom_mu = self.convert2mumap(ctEnergy, self.srcEnergy)
        # self.phantom_mu = self.volRaw.copy()

        return self.phantom_mu

    def convert2mumap_simple(self, fluoEnergy):
        from math import pow, log10
        
        # Data from NIST (Water attenuation coefficient for photon)
        tab_E = [1.00000E-03, 1.50000E-03, 2.00000E-03, 3.00000E-03, 4.00000E-03, 5.00000E-03,  
                6.00000E-03, 8.00000E-03, 1.00000E-02, 1.50000E-02, 2.00000E-02, 3.00000E-02,  
                4.00000E-02, 5.00000E-02, 6.00000E-02, 8.00000E-02, 1.00000E-01, 1.50000E-01,  
                2.00000E-01, 3.00000E-01, 4.00000E-01, 5.00000E-01, 6.00000E-01, 8.00000E-01,  
                1.00000E+00, 1.25000E+00, 1.50000E+00, 2.00000E+00, 3.00000E+00, 4.00000E+00,  
                5.00000E+00, 6.00000E+00, 8.00000E+00, 1.00000E+01, 1.50000E+01, 2.00000E+01]

        water_mu = [4.078E+03, 1.376E+03, 6.173E+02, 1.929E+02, 8.278E+01, 4.258E+01, 
                    2.464E+01, 1.037E+01, 5.329E+00, 1.673E+00, 8.096E-01, 3.756E-01, 
                    2.683E-01, 2.269E-01, 2.059E-01, 1.837E-01, 1.707E-01, 1.505E-01, 
                    1.370E-01, 1.186E-01, 1.061E-01, 9.687E-02, 8.956E-02, 7.865E-02, 
                    7.072E-02, 6.323E-02, 5.754E-02, 4.942E-02, 3.969E-02, 3.403E-02, 
                    3.031E-02, 2.770E-02, 2.429E-02, 2.219E-02, 1.941E-02, 1.813E-02]

        #////////////////////////// Rescale ////////////////////////////////

        # Assuming that the rescale slope is 1.0
        # Find the min HU value 

        HU_min = self.volRaw.min()

        # Correct min value
        HU_delta = -1000.0 - (HU_min)

        #//////////////////////// Get Attenuation Ref values ///////////////

        # fluo
        if fluoEnergy <= tab_E[0]:
            # min value
            mu_water_fluo = water_mu[0]
        elif fluoEnergy >= tab_E[35]:
            # max value
            mu_water_fluo = water_mu[35]
        else:
            # find the energy bin
            index_fluo = 0
            while (tab_E[index_fluo] < fluoEnergy):
                index_fluo += 1
            x0 = tab_E[index_fluo-1]
            x1 = tab_E[index_fluo]

            # loglog interpolation
            y0 = water_mu[index_fluo-1]
            y1 = water_mu[index_fluo]
            x0 = 1.0 / x0
            mu_water_fluo = pow(10.0, log10(y0) + log10(y1/y0)*log10(fluoEnergy*x0)/log10(x1*x0))
        
        #/////////////////// Compute attenuation ///////////////////// 

        return core_convert2mumap_simple(self.volRaw, HU_delta, mu_water_fluo)

    
    def convert2mumap(self, ctEnergy, fluoEnergy):
        from math import pow, log10
        
        # Data from NIST (Water attenuation coefficient for photon)
        tab_E = [1.00000E-03, 1.50000E-03, 2.00000E-03, 3.00000E-03, 4.00000E-03, 5.00000E-03,  
                6.00000E-03, 8.00000E-03, 1.00000E-02, 1.50000E-02, 2.00000E-02, 3.00000E-02,  
                4.00000E-02, 5.00000E-02, 6.00000E-02, 8.00000E-02, 1.00000E-01, 1.50000E-01,  
                2.00000E-01, 3.00000E-01, 4.00000E-01, 5.00000E-01, 6.00000E-01, 8.00000E-01,  
                1.00000E+00, 1.25000E+00, 1.50000E+00, 2.00000E+00, 3.00000E+00, 4.00000E+00,  
                5.00000E+00, 6.00000E+00, 8.00000E+00, 1.00000E+01, 1.50000E+01, 2.00000E+01]

        water_mu = [4.078E+03, 1.376E+03, 6.173E+02, 1.929E+02, 8.278E+01, 4.258E+01, 
                    2.464E+01, 1.037E+01, 5.329E+00, 1.673E+00, 8.096E-01, 3.756E-01, 
                    2.683E-01, 2.269E-01, 2.059E-01, 1.837E-01, 1.707E-01, 1.505E-01, 
                    1.370E-01, 1.186E-01, 1.061E-01, 9.687E-02, 8.956E-02, 7.865E-02, 
                    7.072E-02, 6.323E-02, 5.754E-02, 4.942E-02, 3.969E-02, 3.403E-02, 
                    3.031E-02, 2.770E-02, 2.429E-02, 2.219E-02, 1.941E-02, 1.813E-02]

        bone_mu = [3.781E+03, 1.295E+03, 5.869E+02, 2.958E+02, 1.331E+02, 1.917E+02, 
                    1.171E+02, 5.323E+01, 2.851E+01, 9.032E+00, 4.001E+00, 1.331E+00, 
                    6.655E-01, 4.242E-01, 3.148E-01, 2.229E-01, 1.855E-01, 1.480E-01, 
                    1.309E-01, 1.113E-01, 9.908E-02, 9.022E-02, 8.332E-02, 7.308E-02, 
                    6.566E-02, 5.871E-02, 5.346E-02, 4.607E-02, 3.745E-02, 3.257E-02, 
                    2.946E-02, 2.734E-02, 2.467E-02, 2.314E-02, 2.132E-02, 2.068E-02]

        #////////////////////////// Rescale ////////////////////////////////

        # Assuming that the rescale slope is 1.0
        # Find the min HU value 

        HU_min = self.volRaw.min()

        # Correct min value
        HU_delta = -1000.0 - (HU_min)

        #//////////////////////// Get Attenuation Ref values ///////////////

        # CT
        if ctEnergy <= tab_E[0]:
            # min value
            mu_water_ct = water_mu[0]
            mu_bone_ct  = bone_mu[0]
        elif ctEnergy >= tab_E[35]:
            # max value
            mu_water_ct = water_mu[35]
            mu_bone_ct  = bone_mu[35]
        else:
            # find the energy bin
            index_ct = 0
            while (tab_E[index_ct] < ctEnergy):
                index_ct += 1
            x0 = tab_E[index_ct-1]
            x1 = tab_E[index_ct]

            # loglog interpolation
            y0 = water_mu[index_ct-1]
            y1 = water_mu[index_ct]
            x0 = 1.0 / x0
            mu_water_ct =  pow(10.0, log10(y0) + log10(y1/y0)*log10(ctEnergy*x0)/log10(x1*x0))
            
            y0 = bone_mu[index_ct-1]
            y1 = bone_mu[index_ct]
            mu_bone_ct = pow(10.0, log10(y0) + log10(y1/y0)*log10(ctEnergy*x0)/log10(x1*x0))
        
        # fluo
        if fluoEnergy <= tab_E[0]:
            # min value
            mu_water_fluo = water_mu[0]
            mu_bone_fluo  = bone_mu[0]
        elif fluoEnergy >= tab_E[35]:
            # max value
            mu_water_fluo = water_mu[35]
            mu_bone_fluo  = bone_mu[35]
        else:
            # find the energy bin
            index_fluo = 0
            while (tab_E[index_fluo] < fluoEnergy):
                index_fluo += 1
            x0 = tab_E[index_fluo-1]
            x1 = tab_E[index_fluo]

            # loglog interpolation
            y0 = water_mu[index_fluo-1]
            y1 = water_mu[index_fluo]
            x0 = 1.0 / x0
            mu_water_fluo =  pow(10.0, log10(y0) + log10(y1/y0)*log10(fluoEnergy*x0)/log10(x1*x0))
            
            y0 = bone_mu[index_fluo-1]
            y1 = bone_mu[index_fluo]
            mu_bone_fluo = pow(10.0, log10(y0) + log10(y1/y0)*log10(fluoEnergy*x0)/log10(x1*x0))
        
        #/////////////////// Compute attenuation ///////////////////// 

        # Convert values
        a = mu_water_ct * (mu_bone_fluo - mu_water_fluo)
        b = 1000.0 * (mu_bone_ct - mu_water_ct)
        coef = a / b

        return core_convert2mumap(self.volRaw, HU_delta, mu_water_fluo, coef)

    def getProjection(self):
        from math import pi, cos, sin

        # Move the source
        org_source = np.matrix([[0.0],
                                [self.srcDistIso],
                                [0.0]], 'float32')

        pos_source = self.sysRotX*org_source
        pos_source = self.sysRotZ*pos_source
        pos_source += self.sysTrans

        # Convert in CT-image space
        nx, ny, nz = self.volHeader['shape']
        sx, sy, sz = self.volHeader['spacing']
       
        ctSize = np.matrix([[nx],
                            [ny],
                            [nz]], 'float32')

        ctSpacing = np.matrix([[sx],
                               [sy],
                               [sz]], 'float32')

        # Image space
        pos_source = np.add(pos_source, np.multiply(ctSize, ctSpacing)*0.5)
        pos_source = np.divide(pos_source, ctSpacing)

        # Backward-raycasting
        panel_width   = self.camNx * self.camSx
        panel_height  = self.camNy * self.camSy
        panel_hwidth  = 0.5 * panel_width
        panel_hheight = 0.5 * panel_height

        # Convertion for Numba calculation
        org_pos = np.array([-panel_hwidth + 0.5*self.camSx,
                            -self.camDistIso, 
                             panel_hheight - 0.5*self.camSy], 'float32')


        sysTranslation = self.sysTrans.flatten().A[0]
        pos_source = pos_source.flatten().A[0]
        ctSize = ctSize.flatten().A[0]
        ctSpacing = ctSpacing.flatten().A[0]
        RotX = self.sysRotX.A
        RotZ = self.sysRotZ.A

        image = np.zeros((self.camNy, self.camNx), 'float32')

        projection = core_projection(image, self.phantom_mu, self.camNx, self.camNy, self.camSx, self.camSy, 
                                     org_pos, RotX, RotZ, sysTranslation, pos_source, ctSize, ctSpacing)


        # Post-process
        vmin = projection.min()
        projection -= vmin
        vmax = projection.max()
        if vmax != 0:
            projection /= vmax

        projection = np.exp(-3*projection)

        return projection

        