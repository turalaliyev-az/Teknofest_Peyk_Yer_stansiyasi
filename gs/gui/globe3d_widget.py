"""Uydunun 3D attitude görselleştirmesi (PyOpenGL + QOpenGLWidget)."""
from __future__ import annotations

import math

from OpenGL import GL as gl
from OpenGL import GLU as glu
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QOpenGLWidget


class Globe3DWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 240)
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(50)

    def set_attitude(self, roll: float, pitch: float, yaw: float) -> None:
        self.roll, self.pitch, self.yaw = roll, pitch, yaw

    def initializeGL(self) -> None:  # noqa: N802
        gl.glClearColor(0.05, 0.07, 0.12, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_LIGHT0)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, (3.0, 4.0, 5.0, 0.0))
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, (0.95, 0.95, 0.95, 1.0))
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, (0.35, 0.35, 0.35, 1.0))
        gl.glEnable(gl.GL_COLOR_MATERIAL)
        gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)

    def resizeGL(self, w: int, h: int) -> None:  # noqa: N802
        gl.glViewport(0, 0, max(1, w), max(1, h))

    def paintGL(self) -> None:  # noqa: N802
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        aspect = self.width() / max(1, self.height())

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        glu.gluPerspective(45.0, aspect, 0.1, 100.0)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        glu.gluLookAt(5.0, 4.0, 6.5, 0.0, 0.0, 0.8, 0.0, 0.0, 1.0)

        self._draw_reference()

        gl.glPushMatrix()
        gl.glTranslatef(0.0, 0.0, 2.2)
        gl.glRotatef(-self.yaw, 0.0, 0.0, 1.0)
        gl.glRotatef(self.pitch, 0.0, 1.0, 0.0)
        gl.glRotatef(self.roll, 1.0, 0.0, 0.0)
        self._draw_satellite()
        gl.glPopMatrix()

        # Eksenler uydu konumunda
        gl.glPushMatrix()
        gl.glTranslatef(0.0, 0.0, 2.2)
        self._draw_axes(1.3)
        gl.glPopMatrix()

    # ------------------------------------------------------------------
    # Çizim yardımcıları
    # ------------------------------------------------------------------
    def _draw_reference(self) -> None:
        gl.glDisable(gl.GL_LIGHTING)
        # Dünya (wireframe küre)
        gl.glColor3f(0.16, 0.30, 0.55)
        quad = glu.gluNewQuadric()
        glu.gluQuadricDrawStyle(quad, glu.GLU_LINE)
        glu.gluSphere(quad, 1.0, 40, 24)
        glu.gluDeleteQuadric(quad)
        # Yörünge halkası
        gl.glColor3f(0.35, 0.55, 0.75)
        self._circle(2.2)
        gl.glColor3f(0.30, 0.45, 0.65)
        gl.glPushMatrix()
        gl.glRotatef(30.0, 1.0, 0.0, 0.0)
        self._circle(2.2)
        gl.glPopMatrix()
        gl.glEnable(gl.GL_LIGHTING)

    def _circle(self, radius: float, segments: int = 128) -> None:
        gl.glBegin(gl.GL_LINE_LOOP)
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            gl.glVertex3f(radius * math.cos(a), radius * math.sin(a), 0.0)
        gl.glEnd()

    def _draw_axes(self, length: float) -> None:
        gl.glDisable(gl.GL_LIGHTING)
        gl.glBegin(gl.GL_LINES)
        gl.glColor3f(1.0, 0.0, 0.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(length, 0, 0)
        gl.glColor3f(0.0, 1.0, 0.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(0, length, 0)
        gl.glColor3f(0.0, 0.0, 1.0)
        gl.glVertex3f(0, 0, 0)
        gl.glVertex3f(0, 0, length)
        gl.glEnd()
        gl.glEnable(gl.GL_LIGHTING)

    def _draw_satellite(self) -> None:
        gl.glScalef(0.45, 0.45, 0.45)
        # Merkez gövde
        gl.glColor3f(0.82, 0.82, 0.88)
        self._box(0.8, 0.6, 0.6)
        # Güneş panelleri
        gl.glColor3f(0.15, 0.25, 0.75)
        gl.glPushMatrix()
        gl.glTranslatef(-0.95, 0.0, 0.0)
        self._box(1.1, 0.06, 0.45)
        gl.glPopMatrix()
        gl.glPushMatrix()
        gl.glTranslatef(0.95, 0.0, 0.0)
        self._box(1.1, 0.06, 0.45)
        gl.glPopMatrix()
        # Anten
        gl.glColor3f(0.9, 0.9, 0.9)
        gl.glPushMatrix()
        gl.glTranslatef(0.0, 0.0, 0.4)
        self._cylinder(0.03, 0.03, 0.5, 8)
        gl.glPopMatrix()

    def _box(self, sx: float, sy: float, sz: float) -> None:
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
        gl.glBegin(gl.GL_QUADS)
        # +X
        gl.glNormal3f(1, 0, 0)
        for (y, z) in ((-hy, -hz), (hy, -hz), (hy, hz), (-hy, hz)):
            gl.glVertex3f(hx, y, z)
        # -X
        gl.glNormal3f(-1, 0, 0)
        for (y, z) in ((-hy, -hz), (-hy, hz), (hy, hz), (hy, -hz)):
            gl.glVertex3f(-hx, y, z)
        # +Y
        gl.glNormal3f(0, 1, 0)
        for (x, z) in ((-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)):
            gl.glVertex3f(x, hy, z)
        # -Y
        gl.glNormal3f(0, -1, 0)
        for (x, z) in ((-hx, -hz), (-hx, hz), (hx, hz), (hx, -hz)):
            gl.glVertex3f(x, -hy, z)
        # +Z
        gl.glNormal3f(0, 0, 1)
        for (x, y) in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
            gl.glVertex3f(x, y, hz)
        # -Z
        gl.glNormal3f(0, 0, -1)
        for (x, y) in ((-hx, -hy), (-hx, hy), (hx, hy), (hx, -hy)):
            gl.glVertex3f(x, y, -hz)
        gl.glEnd()

    def _cylinder(self, base_r: float, top_r: float, height: float, segments: int) -> None:
        quad = glu.gluNewQuadric()
        glu.gluCylinder(quad, base_r, top_r, height, segments, 1)
        glu.gluDeleteQuadric(quad)
