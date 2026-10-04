import { test } from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { catalogIdentity,draftInput,profileInput,publishKey } from "../lib/backend-contract";
import { signGuest,verifyGuest } from "../lib/session-token";
const secret="test-secret-32-characters-or-more-123456789";
test("guest session signatures reject tampering, expiry and missing configuration",()=> {
 const id=randomUUID(), token=signGuest(id,secret,1000000000);
 assert.equal(verifyGuest(token,secret,1000000001),id);
 assert.equal(verifyGuest(token+"x",secret,1000000001),null);
 assert.equal(verifyGuest(token,secret,1003000000),null);
 assert.equal(verifyGuest(token,"wrong-secret-that-is-long-enough-1234567",1000000001),null);
 assert.throws(()=>signGuest(id,"short"));
});
test("card identities permit only the application's numeric event/group IDs",()=> {
 assert.deepEqual(catalogIdentity("snowflake:group:7"),{kind:"group",numericId:"7"});
 for(const id of ["demo-1","snowflake:event:0","snowflake:group:1;DELETE","event:1",null])assert.throws(()=>catalogIdentity(id));
});
test("profile validation bounds fields and normalized tags",()=> {
 assert.equal(profileInput({name:" Aayush ",major:"CS",bio:"",availability:"",interests:["AI","AI"]}).name,"Aayush");
 for(const value of [{name:"",major:"CS",bio:"",availability:"",interests:[]},{name:"x",major:"CS",bio:"",availability:"",interests:[123]},{name:"x",major:"CS",bio:"",availability:"",interests:["a,b"]}])assert.throws(()=>profileInput(value));
});
test("publishing validates dates, required fields and idempotency key",()=> {
 const event={kind:"event",title:"Hackathon",description:"",location:"Iribe",date:"2026-10-10",time:"18:00",meetingDetails:"",tags:["AI"]};
 assert.equal(draftInput(event).kind,"event");
 assert.throws(()=>draftInput({...event,date:"2026-02-30"}));
 assert.throws(()=>draftInput({...event,location:""}));
 assert.equal(publishKey(randomUUID()).length,36);
 assert.throws(()=>publishKey("DROP TABLE"));
});
