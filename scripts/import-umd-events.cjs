#!/usr/bin/env node
// Run from the project root: node --env-file=.env.local scripts/import-umd-events.cjs data/umd-events/EVENTS.jsonl
const fs=require('node:fs');
function normalizeEvent(row) {
 if(!row || !/^[a-f0-9]{32}$/.test(row.event_id||'') || typeof row.title!=='string' || !row.title.trim())throw new Error('Invalid event identity/title.');
 if(typeof row.start_time!=='string' || !/(Z|[+-]\d\d:\d\d)$/.test(row.start_time) || !Number.isFinite(Date.parse(row.start_time)))throw new Error('Invalid event timestamp.');
 const url=new URL(row.source_url);if(url.protocol!=='https:')throw new Error('Event source must use HTTPS.');
 const text=row.description || row.short_description || `Hosted by ${row.organizer_name || 'the event organizer'}. See the official listing for details.`;
 const schedule=row.all_day?'\n\nAll-day event; check the official listing for attendance hours.':'';
 return {key:`umd-import:${row.event_id}`,title:row.title.trim(),description:`Official listing: ${url.href}\n\n${text}${schedule}`,location:row.venue_name || row.address || (row.is_online?'Online':'Location listed on official event page'),start:row.start_time,campus:row.is_umd===true?'UMD':'NEAR_UMD',created:row.created_at || row.last_seen_at || new Date().toISOString(),tags:[...new Set((row.tags||[]).map(s=>String(s).trim()).filter(Boolean))]};
}
async function main() {
 const file=process.argv[2];if(!file)throw new Error('Provide the path to EVENTS.jsonl.');
 const rows=fs.readFileSync(file,'utf8').split(/\r?\n/).filter(Boolean).map((s,i)=>{try{return normalizeEvent(JSON.parse(s));}catch{throw new Error(`Invalid event on line ${i+1}; nothing imported.`);}});
 if(new Set(rows.map(r=>r.key)).size!==rows.length)throw new Error('Duplicate IDs in file; nothing imported.');
 const e=process.env;for(const k of ['SNOWFLAKE_ACCOUNT','SNOWFLAKE_USERNAME','SNOWFLAKE_APP_TOKEN','SNOWFLAKE_APP_ROLE','SNOWFLAKE_WAREHOUSE'])if(!e[k])throw new Error(`Missing ${k}.`);
 const names=[e.SNOWFLAKE_DATABASE||'LIFEDATA',e.SNOWFLAKE_SCHEMA||'LIFEDATA'];if(!names.every(n=>/^[A-Za-z_][A-Za-z0-9_]*$/.test(n)))throw new Error('Invalid schema configuration.');const p=names.join('.');
 const sdk=require('snowflake-sdk');sdk.configure({logLevel:'OFF'});
 const c=sdk.createConnection({account:e.SNOWFLAKE_ACCOUNT,username:e.SNOWFLAKE_USERNAME,password:e.SNOWFLAKE_APP_TOKEN,authenticator:'SNOWFLAKE',role:e.SNOWFLAKE_APP_ROLE,warehouse:e.SNOWFLAKE_WAREHOUSE,timeout:15000});
 const q=(sqlText,binds=[])=>new Promise((resolve,reject)=>c.execute({sqlText,binds,complete:(err,_stmt,result)=>err?reject(err):resolve(result||[])}));
 const timer=setTimeout(()=>{console.error('Import timed out; connection closed. Rerun to check completion.');c.destroy(()=>{});process.exit(1)},180000);
 try {
  await new Promise((resolve,reject)=>c.connect(err=>err?reject(err):resolve()));
  await q("ALTER SESSION SET TIMEZONE='UTC'");
  const before=await q(`SELECT COUNT(*) AS N FROM ${p}.EVENTS WHERE APP_ITEM_KEY LIKE 'umd-import:%'`);
  await q('BEGIN TRANSACTION');
  try {
   for(let i=0;i<rows.length;i+=100){
    const batch=JSON.stringify(rows.slice(i,i+100));
    await q(`INSERT INTO ${p}.EVENTS (APP_ITEM_KEY,EVENT_TITLE,EVENT_DESCRIPTION,LOCATION,STARTS_AT,CAMPUS,IS_ACTIVE,IS_DEMO,CREATED_AT)
      SELECT f.VALUE:key::VARCHAR,f.VALUE:title::VARCHAR,f.VALUE:description::VARCHAR,f.VALUE:location::VARCHAR,f.VALUE:start::TIMESTAMP_TZ,f.VALUE:campus::VARCHAR,1,FALSE,f.VALUE:created::TIMESTAMP_TZ
      FROM TABLE(FLATTEN(INPUT=>PARSE_JSON(?))) f
      WHERE NOT EXISTS(SELECT 1 FROM ${p}.EVENTS e WHERE e.APP_ITEM_KEY=f.VALUE:key::VARCHAR)`,[batch]);
   }
   const tags=[...new Set(rows.flatMap(r=>r.tags))];
   await q(`MERGE INTO ${p}.TAGS t USING (SELECT DISTINCT VALUE::VARCHAR AS NAME FROM TABLE(FLATTEN(INPUT=>PARSE_JSON(?)))) s ON t.TAG_NAME=s.NAME WHEN NOT MATCHED THEN INSERT(TAG_NAME) VALUES(s.NAME)`,[JSON.stringify(tags)]);
   for(let i=0;i<rows.length;i+=100){
    await q(`INSERT INTO ${p}.EVENT_TAGS(EVENT_ID,TAG_ID)
     SELECT e.EVENT_ID,MIN(t.TAG_ID) FROM TABLE(FLATTEN(INPUT=>PARSE_JSON(?))) f,
      LATERAL FLATTEN(INPUT=>f.VALUE:tags) tag, ${p}.EVENTS e, ${p}.TAGS t
     WHERE e.APP_ITEM_KEY=f.VALUE:key::VARCHAR AND t.TAG_NAME=tag.VALUE::VARCHAR
      AND NOT EXISTS(SELECT 1 FROM ${p}.EVENT_TAGS et WHERE et.EVENT_ID=e.EVENT_ID AND et.TAG_ID=t.TAG_ID)
     GROUP BY e.EVENT_ID,t.TAG_NAME`,[JSON.stringify(rows.slice(i,i+100))]);
   }
   await q('COMMIT');
  }catch(err){await q('ROLLBACK').catch(()=>{});throw err;}
  const after=await q(`SELECT COUNT(*) AS TOTAL,COUNT_IF(CAMPUS='UMD') AS UMD,COUNT_IF(CAMPUS='UMD' AND STARTS_AT>=CURRENT_TIMESTAMP()) AS UPCOMING_UMD FROM ${p}.EVENTS WHERE APP_ITEM_KEY LIKE 'umd-import:%'`);
  const duplicated=await q(`SELECT APP_ITEM_KEY FROM ${p}.EVENTS WHERE APP_ITEM_KEY LIKE 'umd-import:%' GROUP BY APP_ITEM_KEY HAVING COUNT(*)>1`);
  console.log(JSON.stringify({fileRows:rows.length,inserted:Number(after[0].TOTAL)-Number(before[0].N),...after[0],duplicateKeys:duplicated.length},null,2));
 }catch(err){let message=String(err.message||err);for(const k of ['SNOWFLAKE_APP_TOKEN','SNOWFLAKE_SEARCH_TOKEN','SNOWFLAKE_PASSWORD','SESSION_SECRET'])if(e[k])message=message.split(e[k]).join('[REDACTED]');throw new Error(`Snowflake import failed (${err.code||'unknown'}): ${message.slice(0,1000)}`);}
 finally{clearTimeout(timer);await new Promise(resolve=>c.destroy(()=>resolve()));}
}
module.exports={normalizeEvent};
if(require.main===module)main().catch(err=>{console.error(err.message);process.exitCode=1;});
