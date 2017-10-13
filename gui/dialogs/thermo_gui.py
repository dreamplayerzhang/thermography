import os

import cv2
import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QThread
from PyQt4.QtGui import QImage, QPixmap

import thermography as tg
from gui.design import Ui_ThermoGUI_main_window
from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.webcam_dialog import WebCamWindow


class ThermoGuiThread(QThread):
    iteration_signal = QtCore.pyqtSignal(int)
    finish_signal = QtCore.pyqtSignal(bool)
    last_frame_signal = QtCore.pyqtSignal(np.ndarray)
    edge_frame_signal = QtCore.pyqtSignal(np.ndarray)
    segment_frame_signal = QtCore.pyqtSignal(np.ndarray)
    rectangle_frame_signal = QtCore.pyqtSignal(np.ndarray)
    module_map_frame_signal = QtCore.pyqtSignal(np.ndarray)

    def __init__(self):
        """
        Initializes the Thermo Thread.
        """
        super(ThermoGuiThread, self).__init__()

        self.camera_param_file_name = None
        self.input_file_name = None

        self.pause_time = 50
        self.is_paused = False

        self.webcam_port = None
        self.cap = None
        self.should_use_webcam = False

        self.load_default_paths()

        self.app = tg.App(input_video_path=self.input_file_name, camera_param_file=self.camera_param_file_name)

    def use_webcam(self, webcam_port: int):
        self.webcam_port = webcam_port
        self.cap = cv2.VideoCapture(self.webcam_port)
        self.should_use_webcam = True

    def load_default_paths(self):
        # Load camera parameters.
        settings_dir = tg.settings.get_settings_dir()

        self.camera_param_file_name = os.path.join(settings_dir, "camera_parameters.json")
        tg.settings.set_data_dir("Z:/SE/SEI/Servizi Civili/Del Don Carlo/termografia/")
        self.input_file_name = os.path.join(tg.settings.get_data_dir(), "Ispez Termografica Ghidoni 1.mov")

    def load_video(self, start_frame: int, end_frame: int):
        self.app = tg.App(input_video_path=self.input_file_name, camera_param_file=self.camera_param_file_name)
        self.app.load_video(start_frame=start_frame, end_frame=end_frame)

    def run(self):
        if self.should_use_webcam:
            frame_id = 0
            while True:
                while self.is_paused:
                    self.msleep(self.pause_time)

                ret, frame = self.cap.read()
                if ret:
                    self.app.step(frame_id, frame)

                    self.last_frame_signal.emit(self.app.last_scaled_frame_rgb)
                    self.edge_frame_signal.emit(self.app.last_edges_frame)
                    self.segment_frame_signal.emit(self.app.create_segment_image())
                    self.rectangle_frame_signal.emit(self.app.create_rectangle_image())
                    self.module_map_frame_signal.emit(self.app.create_module_map_image())
                    frame_id += 1

                    self.app.reset()
        else:
            for frame_id, frame in enumerate(self.app.frames):
                while self.is_paused:
                    self.msleep(self.pause_time)

                self.app.step(frame_id, frame)
                self.last_frame_signal.emit(self.app.last_scaled_frame_rgb)
                self.edge_frame_signal.emit(self.app.last_edges_frame)
                self.segment_frame_signal.emit(self.app.create_segment_image())
                self.rectangle_frame_signal.emit(self.app.create_rectangle_image())
                self.module_map_frame_signal.emit(self.app.create_module_map_image())
                self.iteration_signal.emit(frame_id)

                self.app.reset()

        self.finish_signal.emit(True)


class ThermoGUI(QtGui.QMainWindow, Ui_ThermoGUI_main_window):
    """
    Main GUI window.
    """
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.set_logo_icon()

        self.thermo_thread = ThermoGuiThread()
        self.is_stoppable = True

        self.last_folder_opened = None

        self.connect_widgets()
        self.connect_thermo_thread()

        self.capture = None
        self.webcam_port = None

    def set_logo_icon(self):
        gui_path = os.path.join(os.path.join(tg.settings.get_thermography_root_dir(), os.pardir), "gui")
        logo_path = os.path.join(gui_path, "img/logo.png")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(logo_path), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

    def connect_widgets(self):

        # File buttons
        self.file_about.triggered.connect(self.open_about_window)
        self.file_exit.triggered.connect(self.deleteLater)

        # Main buttons.
        self.load_video_button.clicked.connect(self.load_video_from_file)

        self.reset_button.clicked.connect(self.reset_app)
        self.play_video_button.clicked.connect(self.play_all_frames)
        self.stop_video_button.clicked.connect(self.stop_all_frames)
        self.pause_video_button.clicked.connect(self.pause_all_frames)

        self.detect_webcam_button.clicked.connect(self.load_webcam)

        self.image_scaling_slider.valueChanged.connect(self.update_image_scaling)

        # Preprocessing and Edge extraction.
        self.undistort_image_box.stateChanged.connect(self.update_image_distortion)
        self.angle_value.valueChanged.connect(self.update_image_angle)
        self.blur_value.valueChanged.connect(self.update_blur_value)
        self.max_histeresis_value.valueChanged.connect(self.update_histeresis_params)
        self.min_histeresis_value.valueChanged.connect(self.update_histeresis_params)
        self.dilation_value.valueChanged.connect(self.update_dilation_steps)

        # Segment detection.
        self.delta_rho_value.valueChanged.connect(self.update_edge_params)
        self.delta_theta_value.valueChanged.connect(self.update_edge_params)
        self.min_votes_value.valueChanged.connect(self.update_edge_params)
        self.min_length_value.valueChanged.connect(self.update_edge_params)
        self.max_gap_value.valueChanged.connect(self.update_edge_params)
        self.extend_segments_value.valueChanged.connect(self.update_edge_params)

        # Segment clustering.
        self.gmm_value.clicked.connect(self.update_clustering_params)
        self.knn_value.clicked.connect(self.update_clustering_params)
        self.num_clusters_value.valueChanged.connect(self.update_clustering_params)
        self.num_init_value.valueChanged.connect(self.update_clustering_params)
        self.use_angle_value.stateChanged.connect(self.update_clustering_params)
        self.use_centers_value.stateChanged.connect(self.update_clustering_params)
        self.swipe_clusters_value.stateChanged.connect(self.update_clustering_params)

        # Segment cleaning
        self.max_angle_variation_mean_value.valueChanged.connect(self.update_cluster_cleaning_params)
        self.max_merging_angle_value.valueChanged.connect(self.update_cluster_cleaning_params)
        self.max_merging_distance_value.valueChanged.connect(self.update_cluster_cleaning_params)

        # Rectangle detection.
        self.expected_ratio_value.valueChanged.connect(self.update_rectangle_detection_params)
        self.ratio_max_deviation_value.valueChanged.connect(self.update_rectangle_detection_params)
        self.min_area_value.valueChanged.connect(self.update_rectangle_detection_params)

    def connect_thermo_thread(self):
        self.thermo_thread.last_frame_signal.connect(self.display_image)
        self.thermo_thread.edge_frame_signal.connect(self.display_canny_edges)
        self.thermo_thread.segment_frame_signal.connect(self.display_segment_image)
        self.thermo_thread.rectangle_frame_signal.connect(self.display_rectangle_image)
        self.thermo_thread.module_map_frame_signal.connect(self.display_module_map_image)

        self.thermo_thread.finish_signal.connect(self.video_finished)

    def open_about_window(self):
        about = AboutDialog(parent=self)
        about.show()

    def load_video_from_file(self):
        open_directory = ""
        if self.last_folder_opened is not None:
            open_directory = self.last_folder_opened
        video_file_name = QtGui.QFileDialog.getOpenFileName(caption="Select a video",
                                                            filter="Videos (*.mov *.mp4 *.avi)",
                                                            directory=open_directory)
        if video_file_name == "":
            return
        self.last_folder_opened = os.path.dirname(video_file_name)

        self.thermo_thread.input_file_name = video_file_name
        self.is_stoppable = True
        self.setWindowTitle("Thermography: {}".format(video_file_name))

        start_frame = self.video_from_index.value()
        end_frame = self.video_to_index.value()
        if end_frame == -1:
            end_frame = None
        self.thermo_thread.load_video(start_frame=start_frame, end_frame=end_frame)

        self.global_progress_bar.setMinimum(0)
        self.global_progress_bar.setMaximum(len(self.thermo_thread.app.frames) - 1)
        self.thermo_thread.iteration_signal.connect(self.update_global_progress_bar)

    def play_all_frames(self):
        self.thermo_thread.is_paused = False
        self.image_scaling_slider.setEnabled(False)
        self.update_image_scaling()
        self.image_scaling_label.setText("Input image scaling: {:0.2f}".format(self.thermo_thread.app.image_scaling))
        self.play_video_button.setEnabled(False)
        self.pause_video_button.setEnabled(True)
        if self.is_stoppable:
            self.stop_video_button.setEnabled(True)

        self.thermo_thread.start()

    def stop_all_frames(self):
        self.thermo_thread.terminate()
        self.video_finished(True)

    def pause_all_frames(self):
        self.thermo_thread.is_paused = True
        self.play_video_button.setEnabled(True)
        if self.is_stoppable:
            self.stop_video_button.setEnabled(True)
        self.pause_video_button.setEnabled(False)

    def update_global_progress_bar(self, frame_index: int):
        self.global_progress_bar.setValue(frame_index)

    def update_image_scaling(self):
        image_scaling = self.image_scaling_slider.value() * 0.1
        if self.thermo_thread is not None:
            self.thermo_thread.app.image_scaling = image_scaling
        self.image_scaling_label.setText("Input image scaling: {:0.2f}".format(image_scaling))

    def update_histeresis_params(self):
        min_value = self.min_histeresis_value.value()
        max_value = self.max_histeresis_value.value()
        if max_value <= min_value:
            max_value = min_value + 1
        self.max_histeresis_value.setValue(max_value)
        self.thermo_thread.app.edge_detection_parameters.hysteresis_max_thresh = max_value
        self.thermo_thread.app.edge_detection_parameters.hysteresis_min_thresh = min_value

    def update_dilation_steps(self):
        self.thermo_thread.app.edge_detection_parameters.dilation_steps = self.dilation_value.value()

    def update_image_distortion(self):
        self.thermo_thread.app.should_undistort_image = self.undistort_image_box.isChecked()

    def update_image_angle(self):
        self.thermo_thread.app.image_rotating_angle = self.angle_value.value() * np.pi / 180
        if self.angle_value.value() == 360:
            self.angle_value.setValue(0)

    def update_blur_value(self):
        self.thermo_thread.app.gaussian_blur = self.blur_value.value()

    def update_edge_params(self):
        self.thermo_thread.app.segment_detection_parameters.d_rho = self.delta_rho_value.value()
        self.thermo_thread.app.segment_detection_parameters.d_theta = np.pi / 180 * self.delta_theta_value.value()
        self.thermo_thread.app.segment_detection_parameters.min_num_votes = self.min_votes_value.value()
        self.thermo_thread.app.segment_detection_parameters.min_line_length = self.min_length_value.value()
        self.thermo_thread.app.segment_detection_parameters.max_line_gap = self.max_gap_value.value()
        self.thermo_thread.app.segment_detection_parameters.extension_pixels = self.extend_segments_value.value()

    def update_clustering_params(self):
        self.thermo_thread.app.segment_clustering_parameters.num_init = self.num_init_value.value()
        self.thermo_thread.app.segment_clustering_parameters.swipe_clusters = self.swipe_clusters_value.isChecked()
        self.thermo_thread.app.segment_clustering_parameters.num_clusters = self.num_clusters_value.value()
        self.thermo_thread.app.segment_clustering_parameters.use_centers = self.use_centers_value.isChecked()
        self.thermo_thread.app.segment_clustering_parameters.use_angles = self.use_angle_value.isChecked()
        if self.knn_value.isChecked():
            self.thermo_thread.app.segment_clustering_parameters.cluster_type = "knn"
            self.swipe_clusters_value.setEnabled(False)
            self.num_init_value.setEnabled(True)
        elif self.gmm_value.isChecked():
            self.thermo_thread.app.segment_clustering_parameters.cluster_type = "gmm"
            self.swipe_clusters_value.setEnabled(True)
            self.num_init_value.setEnabled(False)

    def update_cluster_cleaning_params(self):
        self.thermo_thread.app.cluster_cleaning_parameters.max_angle_variation_mean = np.pi / 180 * self.max_angle_variation_mean_value.value()
        self.thermo_thread.app.cluster_cleaning_parameters.max_merging_angle = np.pi / 180 * self.max_merging_angle_value.value()
        self.thermo_thread.app.cluster_cleaning_parameters.max_endpoint_distance = np.pi / 180 * self.max_merging_distance_value.value()

    def update_rectangle_detection_params(self):
        self.thermo_thread.app.rectangle_detection_parameters.aspect_ratio = self.expected_ratio_value.value()
        self.thermo_thread.app.rectangle_detection_parameters.aspect_ratio_relative_deviation = self.ratio_max_deviation_value.value()
        self.thermo_thread.app.rectangle_detection_parameters.min_area = self.min_area_value.value()

    def display_image(self, frame: np.ndarray):
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        image = image.scaled(self.video_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(image)
        self.video_view.setPixmap(pixmap)

    def display_canny_edges(self, frame: np.ndarray):
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        image = image.scaled(self.video_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(image)
        self.canny_edges_view.setPixmap(pixmap)

    def display_segment_image(self, frame: np.ndarray):
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        image = image.scaled(self.video_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(image)
        self.segment_image_view.setPixmap(pixmap)

    def display_rectangle_image(self, frame: np.ndarray):
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        image = image.scaled(self.video_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(image)
        self.rectangle_image_view.setPixmap(pixmap)

    def display_module_map_image(self, frame: np.ndarray):
        self.resize_video_view(frame.shape, self.module_image_view)
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.module_image_view.setPixmap(pixmap)

    @staticmethod
    def resize_video_view(size, view):
        view.setFixedSize(size[1], size[0])

    def video_finished(self, finished: bool):
        self.play_video_button.setEnabled(finished)
        self.pause_video_button.setEnabled(not finished)
        self.stop_video_button.setEnabled(not finished)
        self.image_scaling_slider.setEnabled(finished)

    def set_webcam_port(self):
        self.webcam_port = self.capture.webcam_value
        self.thermo_thread.use_webcam(self.webcam_port)
        self.is_stoppable = False
        self.setWindowTitle("Thermography: Webcam")
        self.play_all_frames()

    def load_webcam(self):
        self.capture = WebCamWindow(parent=self)
        self.capture.show()
        self.capture.start()

        self.capture.ok_button.clicked.connect(self.set_webcam_port)
        self.undistort_image_box.setChecked(True)
        self.undistort_image_box.setChecked(False)

    def reset_app(self):
        self.thermo_thread.terminate()
        self.thermo_thread = ThermoGuiThread()
        self.image_scaling_slider.setValue(10)
        self.video_finished(True)
        self.global_progress_bar.setValue(0)
        self.video_view.setText("Input Image")
        self.canny_edges_view.setText("Edges Image")
        self.segment_image_view.setText("Segment Image")
        self.rectangle_image_view.setText("Rectangle Image")
        self.module_image_view.setText("Module Map")
        self.module_image_view.setAlignment(QtCore.Qt.AlignCenter)
        self.capture = None
        self.webcam_port = None

        self.setWindowTitle("Thermography")

        self.connect_thermo_thread()
