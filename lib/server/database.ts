import "server-only";
import type { RowStatement } from "snowflake-sdk";
export type Rows = Record<string, unknown>[];
export type Query = (sql: string, binds?: (string | number | null)[]) => Promise<Rows>;
export const backendEnabled = () => process.env.SNOWFLAKE_BACKEND_ENABLED === "true";
export function databasePrefix() {
  const names = [process.env.SNOWFLAKE_DATABASE || "LIFEDATA", process.env.SNOWFLAKE_SCHEMA || "LIFEDATA"];
  if (!names.every(v => /^[a-z_][a-z0-9_]*$/i.test(v))) throw new Error("Invalid database configuration.");
  return names.map(v=>v.toUpperCase()).join(".");
}
export async function withDatabase<T>(work: (query: Query) => Promise<T>): Promise<T> {
  const e = process.env;
  if (!e.SNOWFLAKE_ACCOUNT || !e.SNOWFLAKE_USERNAME || !e.SNOWFLAKE_APP_TOKEN || !e.SNOWFLAKE_WAREHOUSE || !e.SNOWFLAKE_APP_ROLE || !e.SESSION_SECRET || e.SESSION_SECRET.length < 32) throw new Error("Database is not configured.");
  const { default: sdk } = await import("snowflake-sdk");
  sdk.configure({ logLevel:"OFF" });
  const connection = sdk.createConnection({ account:e.SNOWFLAKE_ACCOUNT, username:e.SNOWFLAKE_USERNAME, password:e.SNOWFLAKE_APP_TOKEN, authenticator:"SNOWFLAKE", warehouse:e.SNOWFLAKE_WAREHOUSE, role:e.SNOWFLAKE_APP_ROLE, timeout:15000, clientSessionKeepAlive:false });
  let closed = false;
  let statement: RowStatement | undefined;
  const query: Query = (sqlText, binds=[]) => new Promise((resolve,reject)=> {
    if (closed) { reject(new Error("Connection closed.")); return; }
    try { statement = connection.execute({ sqlText, binds, complete(error,_stmt,rows) { if (error) reject(new Error("Database query failed.")); else resolve((rows || []) as Rows); } }); }
    catch { reject(new Error("Database query failed.")); }
  });
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_resolve,reject)=> { timer=setTimeout(()=> { closed=true; statement?.cancel(()=>{}); connection.destroy(()=>{}); reject(new Error("Database request timed out.")); },60000); });
  try {
    return await Promise.race([deadline, (async()=> {
      await new Promise<void>((resolve,reject)=> connection.connect(error=> { if (closed || error) { reject(new Error("Database connection failed.")); return; } resolve(); }));
      await query("ALTER SESSION SET TIMEZONE = 'UTC'");
      return work(query);
    })()]);
  } finally { closed=true; clearTimeout(timer); connection.destroy(()=>{}); }
}
export async function transaction<T>(q: Query, work: () => Promise<T>): Promise<T> {
  await q("BEGIN TRANSACTION");
  try { const result=await work(); await q("COMMIT"); return result; }
  catch(error) { await q("ROLLBACK").catch(()=>{}); throw error; }
}

// Serialize guest mutations in this one-server hackathon deployment.
// Standard Snowflake tables do not enforce UNIQUE constraints.
const lockState = globalThis as typeof globalThis & { terplinkGuestLocks?: Map<string,Promise<void>> };
const locks = lockState.terplinkGuestLocks ||= new Map();
export async function withGuestDatabase<T>(key:string, work:(q:Query)=>Promise<T>):Promise<T> {
  const previous=locks.get(key) || Promise.resolve();
  let release!:()=>void;
  const turn=new Promise<void>(resolve=>{release=resolve;});
  const tail=previous.then(()=>turn);
  locks.set(key,tail);
  await previous;
  try{return await withDatabase(work);}
  finally{release();if(locks.get(key)===tail)locks.delete(key);}
}
