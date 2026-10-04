SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'LIFEDATA.LIFEDATA.TERPLINK_SEARCH',
  '{"query":"K-pop BTS dance friends", "columns":["ITEM_ID","TITLE","DESCRIPTION"], "filter":{"@and":[{"@eq":{"CAMPUS":"UMD"}},{"@eq":{"IS_ACTIVE":1}}]}, "limit":2}'
))['results'] AS MATCHES;
