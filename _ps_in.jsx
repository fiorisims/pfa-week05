
app.displayDialogs = DialogModes.NO;
var inFile = new File("C:/Users/missm/Downloads/Untitled_Artwork.psd");
var outFile = new File("C:/Users/missm/AppData/Local/Temp/turnaround_psd_ugd51qrg/Untitled_Artwork_42476068.png");
outFile.encoding = "BINARY";
var doc = app.open(inFile);
__result__ = "";
try {
    try { if (doc.mode !== DocumentMode.RGB) doc.changeMode(ChangeMode.RGB); } catch (e0) {}
    try {
        if (doc.bitsPerChannel !== BitsPerChannelType.EIGHT)
            doc.bitsPerChannel = BitsPerChannelType.EIGHT;
    } catch (e1) {}
    var opts = new PNGSaveOptions();
    opts.interlaced = false;
    doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
    __result__ = "ok";
} catch (e) {
    __result__ = "ERROR " + e;
} finally {
    try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
}
