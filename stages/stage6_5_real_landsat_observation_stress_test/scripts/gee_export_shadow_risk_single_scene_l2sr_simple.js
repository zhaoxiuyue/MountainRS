// Stage 6.5.1-B: simplified shadow-risk single-scene Landsat L2 SR export.
//
// Purpose:
// - Export one low-sun-elevation, QA-usable, full-coverage Landsat 8 C2 L2 SR
//   sample over a mountain small ROI.
// - GEE only checks scene coverage, QA validity, and sun metadata.
// - GEE does NOT compute cos_i, near-zero ratio, shadow ratio, or residuals.
// - Stage 6.5.2-B local processing will decide whether the exported sample is
//   actually suitable for near-zero / shadow mechanism testing.
//
// Boundaries:
// - Do not enter Stage 7.
// - Do not use the old Stage 3 composite.
// - Do not delete or overwrite the Stage 6.5.1-A / 6.5.2-A clean high-sun
//   baseline sample.
//
// If ROI_MTN_NW has no valid candidate, try one backup ROI by editing the
// selected small ROI coordinates below:
// ROI_MTN_W  = [102.88, 30.95, 103.08, 31.15]
// ROI_MTN_C  = [103.00, 31.05, 103.20, 31.25]
// ROI_MTN_SW = [102.82, 30.82, 103.02, 31.02]

var largeLeft = 102.79986111114857;
var largeBottom = 30.800138888885023;
var largeRight = 103.99986111114873;
var largeTop = 31.500138888885115;

// Primary mountain ROI for the B shadow-risk candidate search.
var smallLeft = 102.82;
var smallBottom = 31.18;
var smallRight = 103.02;
var smallTop = 31.38;
var smallRoiName = 'ROI_MTN_NW';

var collectionId = 'LANDSAT/LC08/C02/T1_L2';
var exportCrs = 'EPSG:32648';
var exportScale = 30;
var startDate = '2022-10-01';
var endDate = '2024-03-31';
var geomCoverageThreshold = 0.95;
var validCoverageThreshold = 0.80;
var geometryMaxError = 1;
var previewCandidateCount = 40;

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

print('Stage 6.5.1-B simplified shadow-risk single-scene L2 SR export');
print('GEE only checks low sun angle, ROI coverage, and QA validity. Local Stage 6.5.2-B checks cos_i / near-zero / shadow.');
print('Collection', collectionId);
print('Date range', startDate + ' to ' + endDate);
print('Large ROI bounds', [largeLeft, largeBottom, largeRight, largeTop]);
print('Selected small ROI name', smallRoiName);
print('Selected small ROI bounds', [smallLeft, smallBottom, smallRight, smallTop]);
print('Filtered collection size over selected small ROI', collection.size());

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
    SUN_ELEVATION: image.get('SUN_ELEVATION'),
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
  .sort('SUN_ELEVATION');

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

var validCandidates = candidates
  .filter(ee.Filter.gte('ROI_GEOM_COVERAGE', geomCoverageThreshold))
  .filter(ee.Filter.gte('VALID_PIXEL_COVERAGE', validCoverageThreshold))
  .sort('SUN_ELEVATION');
var hasValidCandidates = validCandidates.size().gt(0);

var validCandidateSummary = ee.FeatureCollection(
  validCandidates
    .limit(previewCandidateCount)
    .toList(previewCandidateCount)
    .map(function(image) {
      return sceneSummaryFeature(ee.Image(image));
    })
);

// Use a valid candidate for export when available. If no valid candidate passes
// the gates, fall back to the first low-sun candidate for map inspection only.
// The evaluate() gate near the bottom prevents export tasks in that case.
var selected = ee.Image(ee.Algorithms.If(
  hasValidCandidates,
  validCandidates.first(),
  candidates.first()
));
var selectedDate = ee.Date(selected.get('system:time_start')).format('YYYY-MM-dd');
var selectedId = selected.get('system:id');
var selectedGeomCoverage = selected.get('ROI_GEOM_COVERAGE');
var selectedValidCoverage = selected.get('VALID_PIXEL_COVERAGE');

print('All candidate table sorted by SUN_ELEVATION ascending', candidateSummary);
print(
  'Valid candidate table sorted by SUN_ELEVATION ascending: ROI_GEOM_COVERAGE >= ' +
    geomCoverageThreshold +
    ', VALID_PIXEL_COVERAGE >= ' +
    validCoverageThreshold,
  validCandidateSummary
);
print('Valid candidate size', validCandidates.size());
print('Selected/display image metadata: lowest SUN_ELEVATION valid candidate if available; otherwise display-only first candidate',
  sceneSummaryFeature(selected));
print('Selected image object', selected);
print(
  'EXPORT SAFETY CHECK: export tasks are created only when valid candidate size > 0. ' +
    'Before clicking RUN, confirm selected metadata is non-empty and coverage values pass thresholds. ' +
    'If the lowest-sun scene is too cloudy in visual preview, manually compare CLOUD_COVER in the valid table.'
);

var red = scaleSrBand(selected, 'SR_B4', 'red');
var nir = scaleSrBand(selected, 'SR_B5', 'nir');
var qaPixel = selected.select('QA_PIXEL').rename('QA_PIXEL');

Map.centerObject(smallRoi, 10);

var largeRoiOutline = ee.FeatureCollection([ee.Feature(largeRoi)]).style({
  color: 'FFFF00',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(largeRoiOutline, {}, 'Large ROI outline');

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
Map.addLayer(nir.clip(smallRoi), {min: 0, max: 0.6, palette: ['black', 'white', 'green']}, 'Selected scaled SR_B5 NIR preview');

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
    small_roi_name: smallRoiName,
    small_roi_left: smallLeft,
    small_roi_bottom: smallBottom,
    small_roi_right: smallRight,
    small_roi_top: smallTop,
    export_crs: exportCrs,
    export_scale: exportScale,
    source_collection: collectionId,
    date_filter_start: startDate,
    date_filter_end: endDate,
    selected_rule: 'lowest SUN_ELEVATION among ROI/QA valid candidates',
    sr_scale_formula: 'reflectance = DN * 0.0000275 - 0.2',
    qa_excluded_bits: 'fill,dilated_cloud,cirrus,cloud,cloud_shadow,snow'
  })
]);

validCandidates.size().evaluate(function(validCount) {
  if (validCount === 0) {
    print('NO EXPORT TASKS CREATED: valid candidate size is 0. Try a backup ROI or adjust the date range.');
    return;
  }

  print('EXPORT TASKS CREATED: valid candidate size =', validCount);

  Export.image.toDrive({
    image: red.clip(smallRoi),
    description: 'stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red',
    fileNamePrefix: 'stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red',
    region: smallRoi,
    crs: exportCrs,
    scale: exportScale,
    maxPixels: 1e13
  });

  Export.image.toDrive({
    image: nir.clip(smallRoi),
    description: 'stage6_5_shadowrisk_single_scene_l8_l2sr_b5_nir',
    fileNamePrefix: 'stage6_5_shadowrisk_single_scene_l8_l2sr_b5_nir',
    region: smallRoi,
    crs: exportCrs,
    scale: exportScale,
    maxPixels: 1e13
  });

  Export.image.toDrive({
    image: qaPixel.clip(smallRoi),
    description: 'stage6_5_shadowrisk_single_scene_l8_l2sr_qa_pixel',
    fileNamePrefix: 'stage6_5_shadowrisk_single_scene_l8_l2sr_qa_pixel',
    region: smallRoi,
    crs: exportCrs,
    scale: exportScale,
    maxPixels: 1e13
  });

  Export.table.toDrive({
    collection: metadata,
    description: 'stage6_5_shadowrisk_single_scene_l8_l2sr_metadata',
    fileNamePrefix: 'stage6_5_shadowrisk_single_scene_l8_l2sr_metadata',
    fileFormat: 'CSV'
  });
});
