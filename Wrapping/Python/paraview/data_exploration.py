r"""
This module is made to provide a set of tools and helper classes for data
exploration for Web deployment.
"""

import math, os, json
from paraview import simple

#==============================================================================
# File Name management
#==============================================================================

class FileNameGenerator():
    """
    This class provide some methods to help build a unique file name
    which map to a given simulation state.
    """

    def __init__(self, working_dir, name_format):
        """
        working_dir: Directory where the generated files should be stored
        name_format: File name pattern using key word like follow:
           {theta}_{phi}.jpg
           {sliceColor}_{slicePosition}.jpg
           {contourBy}_{contourValue}_{theta}_{phi}.jpg
        """
        self.working_dir = working_dir
        self.name_format = name_format
        self.arguments = {}
        self.active_arguments = {}
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

    def set_active_arguments(self, **kwargs):
        """
        Overide all active arguments.
        """
        self.active_arguments = kwargs

    def update_active_arguments(self, **kwargs):
        """
        Update active arguments and extend arguments range.
        """
        for key, value in kwargs.iteritems():
            self.active_arguments[key] = value
            if self.arguments.has_key(key):
                try:
                    self.arguments[key].index(value)
                except ValueError:
                    self.arguments[key].append(value)
            else:
                self.arguments[key] = [value]

    def get_filename(self):
        """
        Return the name of the file based on the current active arguments
        """
        return self.name_format.format(**self.active_arguments)

    def get_fullpath(self):
        """
        Return the full path of the file based on the current active arguments
        """
        return os.path.join(self.working_dir, self.get_filename())

    def WriteMetaData(self):
        """
        Write the info.json file in the working directory which contains
        the metadata of the current file usage with the arguments range.
        """
        jsonObj = {
            "working_dir": self.working_dir,
            "name_pattern": self.name_format,
            "arguments": self.arguments
        }
        metadata_file_path = os.path.join(self.working_dir, "info.json")
        with open(metadata_file_path, "w") as metadata_file:
            metadata_file.write(json.dumps(jsonObj))

#==============================================================================
# Data explorer
#==============================================================================

class SliceExplorer():
    """
    Class use to dump image stack of a data exploration. This data exploration
    is slicing the input data along an axis and save each slice as a new image
    keeping the view normal using parallel projection to disable the projection
    scaling.
    """

    def __init__(self, file_name_generator, view, data, colorBy, lut, steps=10, normal=[0.0,0.0,1.0], bound_range=[0.0, 1.0]):
        """
        file_name_generator: the file name generator to use. Need to have ['sliceColor', 'slicePosition'] as keys.
        view: View proxy to render in
        data: Input proxy to process
        colorBy: ('POINT_DATA', 'RTData')
        lut: Lookup table to use
        steps: Number of slice along the given axis. Default 10
        normal: Slice plane normal. Default [0,0,1]
        bound_range: Array of 2 percentage of the actual data bounds. Default full bounds [0.0, 1.0]
        """
        self.view_proxy = view
        self.slice = simple.Slice( SliceType="Plane", Input=data, SliceOffsetValues=[0.0] )
        self.sliceRepresentation = simple.Show(self.slice)
        self.sliceRepresentation.ColorArrayName = colorBy
        self.sliceRepresentation.LookupTable = lut
        self.slice.SliceType.Normal = normal
        self.dataBounds = data.GetDataInformation().GetBounds()
        self.normal = normal
        self.origin = [ self.dataBounds[0] + bound_range[0] * (self.dataBounds[1] - self.dataBounds[0]),
                        self.dataBounds[2] + bound_range[0] * (self.dataBounds[3] - self.dataBounds[2]),
                        self.dataBounds[4] + bound_range[0] * (self.dataBounds[5] - self.dataBounds[4]) ]
        self.number_of_steps = steps
        ratio = (bound_range[1] - bound_range[0]) / float(steps-1)
        self.origin_inc = [ normal[0] * ratio * (self.dataBounds[1] - self.dataBounds[0]),
                            normal[1] * ratio * (self.dataBounds[3] - self.dataBounds[2]),
                            normal[2] * ratio * (self.dataBounds[5] - self.dataBounds[4]) ]

        # Update file name pattern
        self.file_name_generator = file_name_generator
        self.file_name_generator.update_active_arguments(sliceColor=colorBy[1])

    @staticmethod
    def list_arguments(self):
        return ['sliceColor', 'slicePosition']

    def WriteData(self):
        """
        Probe dataset and dump images to the disk
        """
        self.slice.SMProxy.InvokeEvent('UserEvent', 'HideWidget')
        self.view_proxy.CameraParallelProjection = 1
        self.view_proxy.CameraViewUp = [ self.normal[2], self.normal[0], self.normal[1] ]
        self.view_proxy.CameraFocalPoint = [ 0,0,0 ]
        self.view_proxy.CameraPosition = self.slice.SliceType.Normal
        self.slice.SliceType.Origin = [ (self.dataBounds[0] + self.dataBounds[1])/2,
                                        (self.dataBounds[2] + self.dataBounds[3])/2,
                                        (self.dataBounds[4] + self.dataBounds[5])/2 ]
        simple.Render()
        simple.ResetCamera()

        for step in range(int(self.number_of_steps)):
            self.slice.SliceType.Origin = [ self.origin[0] + float(step) * self.origin_inc[0],
                                            self.origin[1] + float(step) * self.origin_inc[1],
                                            self.origin[2] + float(step) * self.origin_inc[2] ]

            # Update file name pattern
            self.file_name_generator.update_active_arguments(slicePosition=step)
            simple.Render()
            simple.WriteImage(self.file_name_generator.get_fullpath())

        # Generate metadata
        self.file_name_generator.WriteMetaData()
        self.view_proxy.CameraParallelProjection = 0

#==============================================================================

class ContourExplorer():
    """
    Class used to explore data. This Explorer won't dump any images but can be used
    along with the ThreeSixtyImageStackExporter() like in the following example.

        w = simple.Wavelet()

        dataRange = [40.0, 270.0]
        arrayName = ('POINT_DATA', 'RTData')
        fileGenerator = FileNameGenerator('/tmp/iso', '{contourBy}_{contourValue}_{theta}_{phi}.jpg')

        cExplorer = ContourExplorer(fileGenerator, w, arrayName, dataRange, 25)
        proxy = cExplorer.getContour()
        rep = simple.Show(proxy)

        lut = simple.GetLookupTableForArray( "RTData", 1, RGBPoints=[43.34006881713867, 0.23, 0.299, 0.754, 160.01158714294434, 0.865, 0.865, 0.865, 276.68310546875, 0.706, 0.016, 0.15] )
        rep.LookupTable = lut
        rep.ColorArrayName = arrayName
        view = simple.Render()

        exp = ThreeSixtyImageStackExporter(fileGenerator, view, [0,0,0], 100, [0,0,1], [30, 45])
        for progress in cExplorer:
            exp.WriteData()
            print progress
    """

    def __init__(self, file_name_generator, data, contourBy, scalarRange=[0.0, 1.0], steps=10):
        """
        file_name_generator: the file name generator to use. Need to have ['contourBy', 'contourValue'] as keys.
        """
        self.file_name_generator = file_name_generator
        self.contour = simple.Contour(Input=data, ContourBy=contourBy[1], ComputeScalars=1)
        if contourBy[0] == 'POINT_DATA':
            self.data_range = data.GetPointDataInformation().GetArray(contourBy[1]).GetRange()
        else:
            self.data_range = data.GetCellDataInformation().GetArray(contourBy[1]).GetRange()
        self.scalar_origin = scalarRange[0]
        self.scalar_incr = (scalarRange[1] - scalarRange[0]) / float(steps)
        self.number_of_steps = steps
        self.current_step = 0
        # Update file name pattern
        self.file_name_generator.update_active_arguments(contourBy=contourBy[1])

    @staticmethod
    def list_arguments(self):
        return ['contourBy', 'contourValue']

    def __iter__(self):
        return self

    def next(self):
        if self.current_step < self.number_of_steps:
            self.contour.Isosurfaces = [ self.scalar_origin + float(self.current_step)*self.scalar_incr ]
            self.current_step += 1

            # Update file name pattern
            self.file_name_generator.update_active_arguments(contourValue=self.contour.Isosurfaces[0])

            return self.current_step * 100 / self.number_of_steps

        raise StopIteration()

    def reset(self):
        self.current_step = 0

    def getContour(self):
        """
        Return the contour proxy.
        """
        return self.contour

#==============================================================================
# Image exporter
#==============================================================================

class ThreeSixtyImageStackExporter():
    """
    Class use to dump image stack of geometry exploration.
    This exporter will use the provided view to create a 360 view of the visible data.
    """

    def __init__(self, file_name_generator, view_proxy, focal_point=[0.0,0.0,0.0], distance=100.0, rotation_axis=[0,0,1], angular_steps=[10,15]):
        """
        file_name_generator: the file name generator to use. Need to have ['phi', 'theta'] as keys.
        view_proxy: View that will be used for the image captures.
        focal_point=[0.0,0.0,0.0]: Center of rotation and camera focal point.
        distance=100.0: Distance from where the camera should orbit.
        rotation_axis=[0,0,1]: Main axis around which the camera should orbit.
        angular_steps=[10,15]: Phi and Theta angular step in degre. Phi is the angle around
                               the main axis of rotation while Theta is the angle the camera
                               is looking at this axis.
        """
        self.file_name_generator = file_name_generator
        self.angular_steps       = angular_steps
        self.focal_point         = focal_point
        self.distance            = float(distance)
        self.view_proxy          = view_proxy
        self.phi_rotation_axis   = rotation_axis
        try:
            # Z => 0 | Y => 2 | X => 1
            self.offset = (self.phi_rotation_axis.index(1) + 1 ) % 3
        except ValueError:
            raise Exception("Rotation axis not supported", self.phi_rotation_axis)

    @staticmethod
    def list_arguments(self):
        return ['phi', 'theta']

    def WriteData(self):
        """
        Change camera position and dump images to the disk
        """
        self.view_proxy.CameraFocalPoint = self.focal_point
        self.view_proxy.CameraViewUp     = self.phi_rotation_axis
        theta_offset = 90 % self.angular_steps[1]
        if theta_offset == 0:
            theta_offset += self.angular_steps[1]
        for theta in range(-90 + theta_offset, 90 - theta_offset + 1, self.angular_steps[1]):
            theta_rad = float(theta) / 180 * math.pi
            for phi in range(0, 360, self.angular_steps[0]):
                phi_rad = float(phi) / 180 * math.pi

                pos = [
                    float(self.focal_point[0]) - math.cos(phi_rad)   * self.distance * math.cos(theta_rad),
                    float(self.focal_point[1]) + math.sin(phi_rad)   * self.distance * math.cos(theta_rad),
                    float(self.focal_point[2]) + math.sin(theta_rad) * self.distance
                    ]
                up = [
                    + math.cos(phi_rad) * math.sin(theta_rad),
                    - math.sin(phi_rad) * math.sin(theta_rad),
                    + math.cos(theta_rad)
                    ]

                # Handle rotation around Z => 0 | Y => 2 | X => 1
                for i in range(self.offset):
                    pos.insert(0, pos.pop())
                    up.insert(0, up.pop())

                # Apply new camera position
                self.view_proxy.CameraPosition = pos
                self.view_proxy.CameraViewUp = up
                simple.Render()

                # Update file name pattern
                self.file_name_generator.update_active_arguments(phi=phi, theta=(90+theta))
                simple.WriteImage(self.file_name_generator.get_fullpath())

        # Generate metadata
        self.file_name_generator.WriteMetaData()

# -----------------------------------------------------------------------------

def test():
    w = simple.Wavelet()

    dataRange = [40.0, 270.0]
    arrayName = ('POINT_DATA', 'RTData')
    fileGenerator = FileNameGenerator('/tmp/iso', '{contourBy}_{contourValue}_{theta}_{phi}.jpg')

    cExplorer = ContourExplorer(fileGenerator, w, arrayName, dataRange, 25)
    proxy = cExplorer.getContour()
    rep = simple.Show(proxy)

    lut = simple.GetLookupTableForArray( "RTData", 1, RGBPoints=[43.34006881713867, 0.23, 0.299, 0.754, 160.01158714294434, 0.865, 0.865, 0.865, 276.68310546875, 0.706, 0.016, 0.15] )
    rep.LookupTable = lut
    rep.ColorArrayName = arrayName
    view = simple.Render()

    exp = ThreeSixtyImageStackExporter(fileGenerator, view, [0,0,0], 100, [0,0,1], [30, 45])
    for progress in cExplorer:
        exp.WriteData()
        print progress


# -----------------------------------------------------------------------------

def test2():
    w = simple.Wavelet()
    c = simple.Contour(ComputeScalars=1, Isosurfaces=range(50, 250, 10))
    r = simple.Show(c)

    lut = simple.GetLookupTableForArray( "RTData", 1, RGBPoints=[43.34006881713867, 0.23, 0.299, 0.754, 160.01158714294434, 0.865, 0.865, 0.865, 276.68310546875, 0.706, 0.016, 0.15] )
    r.LookupTable = lut
    r.ColorArrayName = ('POINT_DATA','RTData')

    view = simple.Render()
    exp = ThreeSixtyImageStackExporter(FileNameGenerator('/tmp/z', 'w_{theta}_{phi}.jpg'), view, [0,0,0], 100, [0,0,1], [10, 20])
    exp.WriteData()
    exp = ThreeSixtyImageStackExporter(FileNameGenerator('/tmp/y', 'cone_{theta}_{phi}.jpg'), view, [0,0,0], 100, [0,1,0], [10, 20])
    exp.WriteData()
    exp = ThreeSixtyImageStackExporter(FileNameGenerator('/tmp/x', 'cone_{theta}_{phi}.jpg'), view, [0,0,0], 100, [1,0,0], [10, 20])
    exp.WriteData()
    simple.ResetCamera()
    simple.Hide(c)
    slice = SliceExplorer(FileNameGenerator('/tmp/slice', 'w_{sliceColor}_{slicePosition}.jpg'), view, w, ('POINT_DATA','RTData'), lut, 50, [0,1,0])
    slice.WriteData()