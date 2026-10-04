import "server-only";
import { backendEnabled, withGuestDatabase, type Query } from "./database";
import { guestSession } from "./guest";
import { sameOrigin, readJson, reply } from "./http";
import { ensureUser } from "./store";
export async function mutate<T>(request:Request, parse:(body:unknown)=>T, work:(q:Query,userId:string,input:T)=>Promise<unknown>) {
  if(!backendEnabled())return reply({error:"Shared publishing is not enabled."},503);
  let input:T;
  try {sameOrigin(request);input=parse(await readJson(request));} catch{return reply({error:"Check the submitted fields and use the app to submit this request."},400);}
  let key:string;
  try {key=await guestSession();}catch{return reply({error:"Reload the app to start a guest session."},401);}
  try {return reply(await withGuestDatabase(key,async q=>work(q,await ensureUser(q,key),input)));}
  catch{return reply({error:"Your changes could not be saved to Snowflake. Retry; nothing is shown as saved until the server confirms it."},502);}
}
