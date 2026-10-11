// Bridge test: exercises the Photoshop DOM through photoshop_bridge.py.
// Non-destructive - creates a scratch document and closes it without saving.
// Run: python photoshop_bridge.py test_photoshop.jsx

var failures = [];

function check(label, got, want) {
    var ok = (got === want);
    if (!ok) { failures.push(label + ": got " + got + " want " + want); }
    $.writeln((ok ? "ok   " : "FAIL ") + label + "  " + got);
}

$.writeln("--- environment ---");
$.writeln("app: " + app.name + " " + app.version);

var before = app.documents.length;
$.writeln("documents open before: " + before);

$.writeln("--- document + layer round trip ---");
var doc = app.documents.add(256, 256, 72, "bridge_test_doc",
                            NewDocumentMode.RGB, DocumentFill.WHITE);
check("document created", app.documents.length, before + 1);
check("doc name", doc.name, "bridge_test_doc");
check("doc width", doc.width.value, 256);
check("doc height", doc.height.value, 256);
check("active document", app.activeDocument.name, "bridge_test_doc");

var layer = doc.artLayers.add();
layer.name = "bridge_test_layer";
check("layer added", doc.artLayers.length >= 1, true);
check("layer name", doc.layers[0].name, "bridge_test_layer");

$.writeln("--- text output capture ---");
$.writeln("line one");
$.writeln("line two: caf\u00e9 \u2713 " + (7 * 6));

$.writeln("--- non-destructive cleanup ---");
doc.close(SaveOptions.DONOTSAVECHANGES);
check("document closed", app.documents.length, before);

if (failures.length) {
    __result__ = "FAILED: " + failures.join(" | ");
} else {
    __result__ = "all checks passed";
}
