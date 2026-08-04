// Stage 6.5.1-B: shadow-risk single-scene Landsat L2 SR candidate audit.
//
// STAGE 6.5.1-B AUDIT ONLY: no export tasks are created.
//
// Purpose:
// - Search the original DEM large ROI for a single-date Landsat L2 SR candidate
//   that is better suited to testing near-zero / shadow danger mechanisms.
// - Prioritize coverage + QA validity + shadow/near-zero terrain illumination
//   risk, not simply lowest cloud cover.
// - Do not download imagery, do not run residual models, do not enter Stage 7.

var collectionId = 'LANDSAT/LC08/C02/T1_L2';
var startDate = '2022-10-01';
var endDate = '2024-03-31';
var exportCrs = 'EPSG:32648';
var analysisScale = 30;
var geometryMaxError = 1;
var coverageThreshold = 0.95;
var validCoverageThreshold = 0.80;
var previewCandidateCount = 40;

var largeRoi = ee.Geometry.Rectangle(
  [102.79986111114857, 30.800138888885023, 103.99986111114873, 31.500138888885115],
  null,
  false
);

var roiFeatures = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Rectangle([102.82, 31.18, 103.02, 31.38], null, false), {
    roi_name: 'ROI_MTN_NW'
  }),
  ee.Feature(ee.Geometry.Rectangle([102.88, 30.95, 103.08, 31.15], null, false), {
    roi_name: 'ROI_MTN_W'
  }),
  ee.Feature(ee.Geometry.Rectangle([103.00, 31.05, 103.20, 31.25], null, false), {
    roi_name: 'ROI_MTN_C'
  }),
  ee.Feature(ee.Geometry.Rectangle([102.82, 30.82, 103.02, 31.02], null, false), {
    roi_name: 'ROI_MTN_SW'
  })
]);

var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var terrain = ee.Terrain.products(dem);
var slope = terrain.select('slope').rename('slope');
// ee.Terrain.aspect follows the usual downslope aspect convention:
// 0/360 = north, 90 = east, 180 = south, 270 = west.
var aspect = terrain.select('aspect').rename('aspect');

var collection = ee.ImageCollection(collectionId)
  .filterBounds(largeRoi)
  .filterDate(startDate, endDate);

print('STAGE 6.5.1-B AUDIT ONLY: no export tasks are created.');
print('Collection', collectionId);
print('Date range', startDate + ' to ' + endDate);
print('Input image count over large ROI', collection.size());
print('Candidate ROI definitions', roiFeatures);

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

function illuminationForImage(image) {
  image = ee.Image(image);
  var solarAzimuth = ee.Number(image.get('SUN_AZIMUTH'));
  var solarElevation = ee.Number(image.get('SUN_ELEVATION'));
  var solarZenith = ee.Number(90).subtract(solarElevation);

  var slopeRad = slope.multiply(Math.PI / 180.0);
  var aspectRad = aspect.multiply(Math.PI / 180.0);
  var azimuthRad = solarAzimuth.multiply(Math.PI).divide(180.0);
  var zenithRad = solarZenith.multiply(Math.PI).divide(180.0);

  var cosI = slopeRad.cos()
    .multiply(zenithRad.cos())
    .add(
      slopeRad.sin()
        .multiply(zenithRad.sin())
        .multiply(azimuthRad.subtract(aspectRad).cos())
    )
    .rename('cos_i');

  return cosI;
}

function valueOrZero(value) {
  return ee.Number(ee.Algorithms.If(value, value, 0));
}

function metricsForImageRoi(image, roiFeature) {
  image = ee.Image(image);
  roiFeature = ee.Feature(roiFeature);
  var roi = roiFeature.geometry();
  var roiName = roiFeature.get('roi_name');
  var roiArea = roi.area(geometryMaxError);

  var geomCoverage = image.geometry()
    .intersection(roi, geometryMaxError)
    .area(geometryMaxError)
    .divide(roiArea);

  var redMask = image.select('SR_B4').mask().unmask(0);
  var nirMask = image.select('SR_B5').mask().unmask(0);
  var qaClear = clearMaskFromQa(image).unmask(0);
  var validMask = redMask
    .min(nirMask)
    .min(qaClear)
    .rename('valid_mask');

  var cosI = illuminationForImage(image);
  var shadowMask = cosI.lte(0).rename('shadow_mask');
  var nearZeroMask = cosI.lte(0.1).rename('near_zero_mask');
  var safeMask = cosI.gt(0.3).rename('safe_mask');
  var shadowValid = shadowMask.updateMask(validMask).rename('shadow_valid');
  var nearZeroValid = nearZeroMask.updateMask(validMask).rename('near_zero_valid');

  var ratioImage = ee.Image.cat([
    validMask,
    shadowMask,
    nearZeroMask,
    safeMask,
    shadowValid,
    nearZeroValid,
    cosI,
    slope
  ]);

  var means = ratioImage.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: roi,
    crs: exportCrs,
    scale: analysisScale,
    maxPixels: 1e13,
    tileScale: 4
  });

  var mins = cosI.reduceRegion({
    reducer: ee.Reducer.min(),
    geometry: roi,
    crs: exportCrs,
    scale: analysisScale,
    maxPixels: 1e13,
    tileScale: 4
  });

  var slopeP90 = slope.reduceRegion({
    reducer: ee.Reducer.percentile([90]),
    geometry: roi,
    crs: exportCrs,
    scale: analysisScale,
    maxPixels: 1e13,
    tileScale: 4
  });

  var validCoverage = valueOrZero(means.get('valid_mask'));
  var shadowValidRatio = valueOrZero(means.get('shadow_valid'));
  var nearZeroValidRatio = valueOrZero(means.get('near_zero_valid'));
  var score = validCoverage
    .multiply(geomCoverage)
    .multiply(nearZeroValidRatio.add(shadowValidRatio.multiply(2)));

  return ee.Feature(null, {
    roi_name: roiName,
    image_id: image.get('system:id'),
    date: ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
    CLOUD_COVER: image.get('CLOUD_COVER'),
    SUN_AZIMUTH: image.get('SUN_AZIMUTH'),
    SUN_ELEVATION: image.get('SUN_ELEVATION'),
    WRS_PATH: image.get('WRS_PATH'),
    WRS_ROW: image.get('WRS_ROW'),
    ROI_GEOM_COVERAGE: geomCoverage,
    VALID_PIXEL_COVERAGE: validCoverage,
    shadow_ratio: valueOrZero(means.get('shadow_mask')),
    near_zero_ratio: valueOrZero(means.get('near_zero_mask')),
    safe_ratio: valueOrZero(means.get('safe_mask')),
    mean_slope: valueOrZero(means.get('slope')),
    p90_slope: valueOrZero(slopeP90.get('slope_p90')),
    mean_cos_i: valueOrZero(means.get('cos_i')),
    min_cos_i: valueOrZero(mins.get('cos_i')),
    shadow_valid_ratio: shadowValidRatio,
    near_zero_valid_ratio: nearZeroValidRatio,
    score: score
  });
}

function footprintFeature(image) {
  image = ee.Image(image);
  return ee.Feature(image.geometry(), {
    image_id: image.get('system:id'),
    date: ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
    CLOUD_COVER: image.get('CLOUD_COVER'),
    SUN_ELEVATION: image.get('SUN_ELEVATION')
  });
}

var imageList = collection
  .sort('CLOUD_COVER')
  .limit(previewCandidateCount)
  .toList(previewCandidateCount);
var roiList = roiFeatures.toList(roiFeatures.size());

var pairLists = roiList.map(function(roiFeature) {
  roiFeature = ee.Feature(roiFeature);
  return imageList.map(function(image) {
    return metricsForImageRoi(ee.Image(image), roiFeature);
  });
});

var candidateTable = ee.FeatureCollection(ee.List(pairLists).flatten());
var validCandidateTable = candidateTable
  .filter(ee.Filter.gte('ROI_GEOM_COVERAGE', coverageThreshold))
  .filter(ee.Filter.gte('VALID_PIXEL_COVERAGE', validCoverageThreshold));
var topShadowRiskCandidates = validCandidateTable
  .sort('score', false)
  .limit(10);
var hasValidCandidates = validCandidateTable.size().gt(0);
var displayTopCandidates = ee.FeatureCollection(ee.Algorithms.If(
  hasValidCandidates,
  topShadowRiskCandidates,
  candidateTable.sort('score', false).limit(10)
));

print('All image-ROI candidate table', candidateTable);
print('Valid candidate table: ROI_GEOM_COVERAGE >= 0.95 and VALID_PIXEL_COVERAGE >= 0.80', validCandidateTable);
print('Valid candidate count', validCandidateTable.size());
print(ee.Algorithms.If(
  hasValidCandidates,
  'Valid shadow-risk candidates exist. Inspect the top 10 table before creating any later export script.',
  'WARNING: no valid candidates passed the coverage/QA gates. The displayed top candidate is for map inspection only, not for export.'
));
print('Top 10 shadow-risk candidates sorted by score', topShadowRiskCandidates);
print('Recommended candidate metadata if valid candidates exist; otherwise display-only best score',
  ee.Feature(displayTopCandidates.first()));

var footprintList = collection
  .sort('CLOUD_COVER')
  .limit(previewCandidateCount)
  .toList(previewCandidateCount);
var candidateFootprints = ee.FeatureCollection(
  footprintList.map(function(image) {
    return footprintFeature(ee.Image(image));
  })
);

var topFeature = ee.Feature(displayTopCandidates.first());
var topImage = ee.Image(collection.filter(ee.Filter.eq('system:id', topFeature.get('image_id'))).first());
var topRoi = ee.Feature(roiFeatures.filter(ee.Filter.eq('roi_name', topFeature.get('roi_name'))).first());
var topCosI = illuminationForImage(topImage).clip(topRoi.geometry());
var topNearZero = topCosI.lte(0.1).selfMask().clip(topRoi.geometry());
var topShadow = topCosI.lte(0).selfMask().clip(topRoi.geometry());

Map.centerObject(largeRoi, 9);

var largeRoiOutline = ee.FeatureCollection([ee.Feature(largeRoi)]).style({
  color: 'FFFF00',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(largeRoiOutline, {}, 'Large ROI outline');

var smallRoiOutlines = roiFeatures.style({
  color: 'FF6600',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(smallRoiOutlines, {}, 'Candidate small ROIs');

var candidateFootprintOutlines = candidateFootprints.style({
  color: '00FFFF',
  fillColor: '00000000',
  width: 2
});
Map.addLayer(candidateFootprintOutlines, {}, 'Candidate footprints');

var topImageFootprint = ee.FeatureCollection([ee.Feature(topImage.geometry())]).style({
  color: '0000FF',
  fillColor: '00000000',
  width: 3
});
Map.addLayer(topImageFootprint, {}, 'Top candidate footprint');

var topRoiOutline = ee.FeatureCollection([topRoi]).style({
  color: 'FF0000',
  fillColor: '00000000',
  width: 4
});
Map.addLayer(topRoiOutline, {}, 'Top candidate ROI');
Map.addLayer(topCosI, {min: -0.5, max: 1.0, palette: ['0015ff', 'ffffff', 'ff0000']}, 'Top candidate cos_i preview');
Map.addLayer(topNearZero, {palette: ['ffff00']}, 'Top candidate near-zero mask');
Map.addLayer(topShadow, {palette: ['000000']}, 'Top candidate shadow mask');
