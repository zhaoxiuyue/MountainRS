// Stage 6.5.1: Clean single-scene Landsat 8 C2 L2 SR export preparation.
//
// Purpose:
// - Prepare one clean single-date Landsat Level-2 Surface Reflectance package
//   for Stage 6.5 real-observation stress testing.
// - This is not Stage 7 multi-scene / multi-ROI validation.
// - Do not train models, do not run inversion, do not use the old Stage 3
//   composite as a single-day physical validation sample.
//
// Export safety:
// - Inspect the candidate summary table first.
// - Only run export tasks if the selected scene has:
//   ROI_GEOM_COVERAGE >= 0.95
//   VALID_PIXEL_COVERAGE >= 0.90, preferably >= 0.95
// - If no candidate passes, adjust date range or small ROI. Do not export a
//   partial or cloudy sample.

var largeLeft = 102.79986111114857;
var largeBottom = 30.800138888885023;
var largeRight = 103.99986111114873;
var largeTop = 31.500138888885115;

// Small ROI for a clean single-scene stress-test sample.
// It stays within the original DEM extent and is intentionally smaller than
// the Stage 3 large ROI to make full single-scene coverage realistic.
var smallLeft = 103.72;
var smallBottom = 30.90;
var smallRight = 103.92;
var smallTop = 31.10;

var collectionId = 'LANDSAT/LC08/C02/T1_L2';
var exportCrs = 'EPSG:32648';
var exportScale = 30;
var startDate = '2023-04-01';
var endDate = '2023-10-31';
var geomCoverageThreshold = 0.95;
var validCoverageThreshold = 0.90;
var preferredValidCoverageThreshold = 0.95;
var geometryMaxError = 1;
var previewCandidateCount = 20;

var largeRoi = ee.Geometry.Rectangle(
  [largeLeft, largeBottom, largeRight, largeTop],
  null,
  false
);
var smallRoi = ee.Geometry.Rectangle(
  [smallLeft, smallBottom, smallRight, smallTop],
  null,
  false
);
var smallRoiArea = smallRoi.area(geometryMaxError);

var collection = ee.ImageCollection(collectionId)
  .filterBounds(smallRoi)
  .filterDate(startDate, endDate);

print('Stage 6.5.1 clean single-scene L2 SR export preparation');
print('Collection', collectionId);
print('Date range', startDate + ' to ' + endDate);
print('Large ROI bounds', [largeLeft, largeBottom, largeRight, largeTop]);
print('Small ROI bounds', [smallLeft, smallBottom, smallRight, smallTop]);
print('Filtered collection size over small ROI', collection.size());

function clearMaskFromQa(image) {
  var qa = image.select('QA_PIXEL');
  var fill = qa.bitwiseAnd(1 << 0).eq(0);
  var dilatedCloud = qa.bitwiseAnd(1 << 1).eq(0);
  var cirrus = qa.bitwiseAnd(1 << 2).eq(0);
  var cloud = qa.bitwiseAnd(1 << 3).eq(0);
  var cloudShadow = qa.bitwiseAnd(1 << 4).eq(0);
  var snow = qa.bitwiseAnd(1 << 5).eq(0);
  return fill
    .and(dilatedCloud)
    .and(cirrus)
    .and(cloud)
    .and(cloudShadow)
    .and(snow)
    .rename('qa_clear');
}

function addCoverageMetrics(image) {
  image = ee.Image(image);

  var intersection = image.geometry().intersection(smallRoi, geometryMaxError);
  var geomCoverage = intersection.area(geometryMaxError).divide(smallRoiArea);

  var redMask = image.select('SR_B4').mask().unmask(0);
  var nirMask = image.select('SR_B5').mask().unmask(0);
  var qaClear = clearMaskFromQa(image).unmask(0);
  var bothValid = redMask
    .min(nirMask)
    .min(qaClear)
    .rename('both_valid');

  var validCoverage = bothValid.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: smallRoi,
    crs: exportCrs,
    scale: exportScale,
    maxPixels: 1e13,
    tileScale: 4
  }).get('both_valid');

  return image.set({
    ROI_GEOM_COVERAGE: geomCoverage,
    VALID_PIXEL_COVERAGE: validCoverage
  });
}

function sceneSummaryFeature(image) {
  image = ee.Image(image);
  return ee.Feature(null, {
    image_id: image.get('system:id'),
    date: ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
    CLOUD_COVER: image.get('CLOUD_COVER'),
    SUN_AZIMUTH: image.get('SUN_AZIMUTH'),
    SUN_ELEVATION: image.get('SUN_ELEVATION'),
    WRS_PATH: image.get('WRS_PATH'),
    WRS_ROW: image.get('WRS_ROW'),
    ROI_GEOM_COVERAGE: image.get('ROI_GEOM_COVERAGE'),
    VALID_PIXEL_COVERAGE: image.get('VALID_PIXEL_COVERAGE')
  });
}

function footprintFeature(image) {
  image = ee.Image(image);
  return ee.Feature(image.geometry(), {
    image_id: image.get('system:id'),
    date: ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
    CLOUD_COVER: image.get('CLOUD_COVER'),
    ROI_GEOM_COVERAGE: image.get('ROI_GEOM_COVERAGE'),
    VALID_PIXEL_COVERAGE: image.get('VALID_PIXEL_COVERAGE')
  });
}

function scaleSrBand(image, bandName, outputName) {
  return image
    .select(bandName)
    .multiply(0.0000275)
    .add(-0.2)
    .rename(outputName)
    .toFloat();
}

var candidates = collection
  .map(addCoverageMetrics)
  .sort('CLOUD_COVER');

var candidateList = candidates
  .limit(previewCandidateCount)
  .toList(previewCandidateCount);

var candidateSummary = ee.FeatureCollection(
  candidateList.map(function(image) {
    return sceneSummaryFeature(ee.Image(image));
  })
);

var candidateFootprints = ee.FeatureCollection(
  candidateList.map(function(image) {
    return footprintFeature(ee.Image(image));
  })
);

print('Candidate summary table sorted by CLOUD_COVER', candidateSummary);

var validCandidates = candidates
  .filter(ee.Filter.gte('ROI_GEOM_COVERAGE', geomCoverageThreshold))
  .filter(ee.Filter.gte('VALID_PIXEL_COVERAGE', validCoverageThreshold))
  .sort('CLOUD_COVER');

var preferredCandidates = validCandidates
  .filter(ee.Filter.gte('VALID_PIXEL_COVERAGE', preferredValidCoverageThreshold))
  .sort('CLOUD_COVER');

print(
  'Valid candidate size: ROI_GEOM_COVERAGE >= ' +
    geomCoverageThreshold +
    ', VALID_PIXEL_COVERAGE >= ' +
    validCoverageThreshold,
  validCandidates.size()
);
print(
  'Preferred candidate size: VALID_PIXEL_COVERAGE >= ' +
    preferredValidCoverageThreshold,
  preferredCandidates.size()
);

var selected = ee.Image(validCandidates.first());
var selectedDate = ee.Date(selected.get('system:time_start')).format('YYYY-MM-dd');
var selectedId = selected.get('system:id');
var selectedGeomCoverage = selected.get('ROI_GEOM_COVERAGE');
var selectedValidCoverage = selected.get('VALID_PIXEL_COVERAGE');

print('Selected image', selected);
print('Selected image metadata', sceneSummaryFeature(selected));
print(
  'EXPORT SAFETY CHECK: only run tasks if selected metadata is non-empty, ROI_GEOM_COVERAGE >= ' +
    geomCoverageThreshold +
    ', and VALID_PIXEL_COVERAGE >= ' +
    validCoverageThreshold +
    ' (preferably >= ' +
    preferredValidCoverageThreshold +
    ').'
);

var red = scaleSrBand(selected, 'SR_B4', 'red');
var nir = scaleSrBand(selected, 'SR_B5', 'nir');
var qaPixel = selected.select('QA_PIXEL').rename('QA_PIXEL');
var ndviPreview = nir.subtract(red).divide(nir.add(red)).rename('NDVI_preview');

Map.centerObject(smallRoi, 10);

var largeRoiOutline = ee.FeatureCollection([ee.Feature(largeRoi)]).style({
  color: 'FFFF00',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(largeRoiOutline, {}, 'Original large ROI outline');

var smallRoiOutline = ee.FeatureCollection([ee.Feature(smallRoi)]).style({
  color: 'FF0000',
  fillColor: '00000000',
  width: 3
});
Map.addLayer(smallRoiOutline, {}, 'Selected small ROI outline');

var candidateFootprintOutlines = candidateFootprints.style({
  color: '00FFFF',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(candidateFootprintOutlines, {}, 'Candidate footprints');

var selectedFootprint = ee.FeatureCollection([ee.Feature(selected.geometry())]).style({
  color: '0000FF',
  fillColor: '00000000',
  width: 3
});
Map.addLayer(selectedFootprint, {}, 'Selected image footprint');

Map.addLayer(red.clip(smallRoi), {min: 0, max: 0.4, palette: ['black', 'red']}, 'Selected scaled SR_B4 red');
Map.addLayer(nir.clip(smallRoi), {min: 0, max: 0.6, palette: ['black', 'green']}, 'Selected scaled SR_B5 NIR');
Map.addLayer(ndviPreview.clip(smallRoi), {min: -0.2, max: 0.8, palette: ['brown', 'white', 'green']}, 'Selected NDVI preview');

var metadata = ee.FeatureCollection([
  ee.Feature(null, {
    image_id: selectedId,
    date: selectedDate,
    CLOUD_COVER: selected.get('CLOUD_COVER'),
    SUN_AZIMUTH: selected.get('SUN_AZIMUTH'),
    SUN_ELEVATION: selected.get('SUN_ELEVATION'),
    WRS_PATH: selected.get('WRS_PATH'),
    WRS_ROW: selected.get('WRS_ROW'),
    ROI_GEOM_COVERAGE: selectedGeomCoverage,
    VALID_PIXEL_COVERAGE: selectedValidCoverage,
    large_roi_left: largeLeft,
    large_roi_bottom: largeBottom,
    large_roi_right: largeRight,
    large_roi_top: largeTop,
    small_roi_left: smallLeft,
    small_roi_bottom: smallBottom,
    small_roi_right: smallRight,
    small_roi_top: smallTop,
    export_crs: exportCrs,
    export_scale: exportScale,
    source_collection: collectionId,
    date_filter_start: startDate,
    date_filter_end: endDate,
    sr_scale_formula: 'reflectance = DN * 0.0000275 - 0.2',
    qa_excluded_bits: 'fill,dilated_cloud,cirrus,cloud,cloud_shadow,snow'
  })
]);

Export.image.toDrive({
  image: red.clip(smallRoi),
  description: 'stage6_5_clean_single_l8_l2sr_b4_red',
  fileNamePrefix: 'stage6_5_clean_single_l8_l2sr_b4_red',
  region: smallRoi,
  crs: exportCrs,
  scale: exportScale,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: nir.clip(smallRoi),
  description: 'stage6_5_clean_single_l8_l2sr_b5_nir',
  fileNamePrefix: 'stage6_5_clean_single_l8_l2sr_b5_nir',
  region: smallRoi,
  crs: exportCrs,
  scale: exportScale,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: qaPixel.clip(smallRoi),
  description: 'stage6_5_clean_single_l8_l2sr_qa_pixel',
  fileNamePrefix: 'stage6_5_clean_single_l8_l2sr_qa_pixel',
  region: smallRoi,
  crs: exportCrs,
  scale: exportScale,
  maxPixels: 1e13
});

Export.table.toDrive({
  collection: metadata,
  description: 'stage6_5_clean_single_l8_l2sr_metadata',
  fileNamePrefix: 'stage6_5_clean_single_l8_l2sr_metadata',
  fileFormat: 'CSV'
});
