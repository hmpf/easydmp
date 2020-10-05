from rest_framework.renderers import BaseRenderer

from easydmp.lib.graphviz import render_dotsource_to_bytes


__all__ = [
    'PDFRenderer',
    'PNGRenderer',
    'SVGRenderer',
    'DOTRenderer',
    'DotPDFRenderer',
    'DotPNGRenderer',
    'DotSVGRenderer',
    'DotDOTRenderer',
]


class BaseBinaryRenderer(BaseRenderer):
    charset = None
    render_style = 'binary'


class PDFRenderer(BaseBinaryRenderer):
    """DRF renderer for PDF binary content"""
    media_type = 'application/pdf'
    format = 'pdf'


class PNGRenderer(BaseBinaryRenderer):
    """DRF renderer for PNG binary content"""
    media_type = 'image/png'
    format = 'png'


class SVGRenderer(BaseRenderer):
    """DRF renderer for SVG"""
    media_type = 'image/svg+xml'
    format = 'svg'
    charset = 'utf-8'


class DOTRenderer(BaseRenderer):
    """DRF renderer for graphviz"""
    media_type = 'text/vnd.graphviz'
    format = 'dot'
    charset = 'utf-8'


class DotMixin:

    def render(self, data, media_type=None, renderer_context=None):
        return render_dotsource_to_bytes(self.format, data)


class DotPDFRenderer(DotMixin, PDFRenderer):
    pass


class DotPNGRenderer(DotMixin, PNGRenderer):
    pass


class DotSVGRenderer(DotMixin, SVGRenderer):
    pass


class DotDOTRenderer(DotMixin, DOTRenderer):
    pass
