import {test} from "node:test";
import assert from "node:assert/strict";
import {createRequire} from "node:module";
const {normalizeEvent}=createRequire(import.meta.url)("../scripts/import-umd-events.cjs");
const event={event_id:"a".repeat(32),title:"Real campus event",start_time:"2026-11-20T18:00:00-05:00",source_url:"https://calendar.umd.edu/events/test",is_umd:true,tags:["technology","technology"],description:null};
test("import keeps stable identity, explicit timezone, official source and deduplicated tags",()=>{
 const row=normalizeEvent(event);assert.equal(row.key,"umd-import:"+event.event_id);assert.equal(row.start,event.start_time);assert.equal(row.campus,"UMD");assert.deepEqual(row.tags,["technology"]);assert.match(row.description,/Official listing: https/);
});
test("off-campus data stays separate and malformed rows fail before import",()=>{
 assert.equal(normalizeEvent({...event,is_umd:false}).campus,"NEAR_UMD");
 for(const change of [{event_id:"bad"},{start_time:"tomorrow"},{source_url:"javascript:alert(1)"},{title:""}])assert.throws(()=>normalizeEvent({...event,...change}));
});
