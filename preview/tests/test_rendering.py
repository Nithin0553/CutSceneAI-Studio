from xml.etree import ElementTree

from cutsceneai_preview import PreviewManifest, render_storyboard_svg


def test_storyboard_svg_is_well_formed(preview_manifest: PreviewManifest) -> None:
    svg = render_storyboard_svg(preview_manifest)
    root = ElementTree.fromstring(svg)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert "Office Dialogue" in svg
    assert "shot-establishing" in svg
    assert "Mina" in svg
