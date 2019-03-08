from rest_framework.renderers import BaseRenderer


__all__ = [
    'PDFRenderer',
    'PNGRenderer',
    'SVGRenderer',
    'DOTRenderer'
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
