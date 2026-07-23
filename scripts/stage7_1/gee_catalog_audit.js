// Stage 7.1 prospective catalog auditor.
// This file is intentionally not executed by the First Action.

'use strict';

var COLLECTION_ID = 'LANDSAT/LC08/C02/T1_L2';
var START_UTC = '2023-01-01T00:00:00Z';
var END_UTC = '2024-01-01T00:00:00Z';
var WRS_PATH = 130;
var WRS_ROW = 38;
var TARGET_CRS = 'EPSG:32648';
var TARGET_TRANSFORM = [30, 0, 292230, 0, -30, 3473790];
var TARGET_PIXEL_COUNT = 488800;
var MIN_FOOTPRINT_COVERAGE = 0.999999;

var targetRoi = ee.Geometry.Rectangle(
  [292230, 3451230, 311730, 3473790],
  TARGET_CRS,
  false
);
var targetAreaM2 = targetRoi.area(1);

function stableSortKey(image) {
  var timestamp = ee.Date(image.get('system:time_start'))
    .format("YYYY-MM-dd'T'HH:mm:ss.SSS'Z'", 'UTC');
  return timestamp.cat('|').cat(ee.String(image.get('system:index')));
}

function withFootprintCoverage(image) {
  var footprint = image.geometry();
  var intersectionAreaM2 = footprint.intersection(targetRoi, 1).area(1);
  var coverage = intersectionAreaM2.divide(targetAreaM2);
  return image.set({
    target_roi_area_m2: targetAreaM2,
    target_roi_intersection_area_m2: intersectionAreaM2,
    target_roi_footprint_coverage: coverage,
    stable_sort_key: stableSortKey(image)
  });
}

function qaAndCoverageSummary(image) {
  var qa = image.select('QA_PIXEL');
  var scaled = image
    .select(['SR_B4', 'SR_B5'])
    .multiply(0.0000275)
    .add(-0.2);

  var qaClear = qa.bitwiseAnd(63).eq(0).rename('qa_clear_count');
  var water = qa.bitwiseAnd(1 << 7).neq(0).rename('qa_water_count');
  var sourceMaskValid = scaled.mask().reduce(ee.Reducer.min());
  var reflectanceInRange = scaled
    .gte(-0.05)
    .and(scaled.lte(1.0))
    .reduce(ee.Reducer.min());
  var numericValid = sourceMaskValid
    .and(reflectanceInRange)
    .rename('reflectance_numeric_valid_count');
  var baseValid = qaClear.and(numericValid).rename('base_valid_count');
  var baseValidLand = baseValid
    .and(water.not())
    .rename('base_valid_land_count');

  var summaryImage = ee.Image.cat([
    ee.Image.constant(1).rename('target_pixel_count'),
    qaClear,
    water,
    numericValid,
    baseValid,
    baseValidLand,
    qa.bitwiseAnd(1 << 0).neq(0).rename('qa_fill_count'),
    qa.bitwiseAnd(1 << 1).neq(0).rename('qa_dilated_cloud_count'),
    qa.bitwiseAnd(1 << 2).neq(0).rename('qa_cirrus_count'),
    qa.bitwiseAnd(1 << 3).neq(0).rename('qa_cloud_count'),
    qa.bitwiseAnd(1 << 4).neq(0).rename('qa_cloud_shadow_count'),
    qa.bitwiseAnd(1 << 5).neq(0).rename('qa_snow_count')
  ]).unmask(0);

  return summaryImage.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: targetRoi,
    crs: TARGET_CRS,
    crsTransform: TARGET_TRANSFORM,
    maxPixels: 1000000,
    tileScale: 4
  });
}

var requiredExportableProperties = [
  'system:index',
  'system:time_start',
  'SPACECRAFT_ID',
  'SENSOR_ID',
  'PROCESSING_LEVEL',
  'WRS_PATH',
  'WRS_ROW',
  'SUN_AZIMUTH',
  'SUN_ELEVATION'
];

var scoped = ee.ImageCollection(COLLECTION_ID)
  .filterDate(START_UTC, END_UTC)
  .filter(ee.Filter.eq('WRS_PATH', WRS_PATH))
  .filter(ee.Filter.eq('WRS_ROW', WRS_ROW))
  .map(withFootprintCoverage);

var cataloged = scoped
  .filter(
    ee.Filter.gte(
      'target_roi_footprint_coverage',
      MIN_FOOTPRINT_COVERAGE
    )
  )
  .sort('stable_sort_key');

var exportable = cataloged.filter(
  ee.Filter.notNull(requiredExportableProperties)
);
var exportableIds = ee.List(exportable.aggregate_array('system:index'));
var catalogedList = cataloged.toList(cataloged.size());

var candidateCatalog = ee.FeatureCollection(
  catalogedList.map(function (item) {
    var image = ee.Image(item);
    var isExportable = exportableIds.contains(image.get('system:index'));
    var state = ee.String(
      ee.Algorithms.If(isExportable, 'exportable', 'cataloged')
    );
    var fullAssetId = ee.String(COLLECTION_ID)
      .cat('/')
      .cat(ee.String(image.get('system:index')));
    var properties = ee.Dictionary({
      observation_schema: 'mountainrs-stage7.1-observation-record-v1',
      candidate_state: state,
      acquisition_id: fullAssetId,
      earth_engine_asset_id: fullAssetId,
      system_index: image.get('system:index'),
      system_time_start_ms: image.get('system:time_start'),
      system_time_start_utc: ee.Date(image.get('system:time_start'))
        .format("YYYY-MM-dd'T'HH:mm:ss.SSS'Z'", 'UTC'),
      platform: image.get('SPACECRAFT_ID'),
      sensor: image.get('SENSOR_ID'),
      collection: COLLECTION_ID,
      tier: 'T1',
      processing_level: image.get('PROCESSING_LEVEL'),
      wrs_path: image.get('WRS_PATH'),
      wrs_row: image.get('WRS_ROW'),
      sun_azimuth_deg: image.get('SUN_AZIMUTH'),
      sun_elevation_deg: image.get('SUN_ELEVATION'),
      sun_azimuth_source_field: 'SUN_AZIMUTH',
      sun_elevation_source_field: 'SUN_ELEVATION',
      cloud_cover_report_only: image.get('CLOUD_COVER'),
      source_footprint_area_m2: image.geometry().area(1),
      target_roi_area_m2: image.get('target_roi_area_m2'),
      target_roi_intersection_area_m2: image.get(
        'target_roi_intersection_area_m2'
      ),
      target_roi_footprint_coverage: image.get(
        'target_roi_footprint_coverage'
      ),
      target_grid_id: 'shadow-risk-b-b4-grid-v1',
      target_crs: TARGET_CRS,
      target_transform: TARGET_TRANSFORM,
      target_pixel_count_declared: TARGET_PIXEL_COUNT,
      stable_sort_key: image.get('stable_sort_key'),
      stack_eligible: 'not_evaluated_local_only',
      model_eligible: 'not_adjudicated_stage_7_2'
    }).combine(qaAndCoverageSummary(image), true);
    return ee.Feature(image.geometry(), properties);
  })
).sort('stable_sort_key');

print('Frozen Stage 7.1 scope', {
  collection: COLLECTION_ID,
  start_utc_inclusive: START_UTC,
  end_utc_exclusive: END_UTC,
  wrs_path: WRS_PATH,
  wrs_row: WRS_ROW,
  target_crs: TARGET_CRS,
  target_transform: TARGET_TRANSFORM,
  minimum_footprint_coverage: MIN_FOOTPRINT_COVERAGE
});
print('Cataloged acquisition count', cataloged.size());
print('Exportable acquisition count', exportable.size());
print('Complete structured candidate catalog', candidateCatalog);
