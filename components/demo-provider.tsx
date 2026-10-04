"use client";
import { createContext,useContext,useEffect,useRef,useState,type ReactNode } from "react";
import { readDemo,writeDemo } from "@/lib/storage";
import { freshDemo } from "@/lib/seeds";
import { mergeSearchCards } from "@/lib/recommendations";
import type { CampusItem,Decision,DemoState,Draft,Profile } from "@/lib/types";
interface DemoContextValue {
  state:DemoState|null; ready:boolean; resetVersion:number; error:string; mode:"local"|"snowflake"; pending:boolean;
  addItem:(draft:Draft)=>Promise<boolean>; decide:(id:string,decision:Decision)=>Promise<boolean>;
  saveProfile:(profile:Profile)=>Promise<boolean>; reset:()=>Promise<boolean>;
  importSearchCards:(items:CampusItem[])=>boolean; refresh:()=>Promise<void>;
}
const Context=createContext<DemoContextValue|null>(null);
export function DemoProvider({children}:{children:ReactNode}) {
  const [state,setState]=useState<DemoState|null>(null),[ready,setReady]=useState(false),[error,setError]=useState(""),[mode,setMode]=useState<"local"|"snowflake">("local"),[pending,setPending]=useState(false),[resetVersion,setResetVersion]=useState(0);
  const current=useRef<DemoState|null>(null),live=useRef(false),locked=useRef(false),generation=useRef(0);
  const attempts=useRef(new Map<string,string>());
  function publishState(next:DemoState) {current.current=next;setState(next);setError("");}
  async function api(path:string,body?:unknown) {
    const response=await fetch(path,body===undefined?{cache:"no-store"}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const result=await response.json(); if(!response.ok)throw new Error(result.error || "The server could not save this change.");return result;
  }
  const initialRequest=useRef<ReturnType<typeof api>|null>(null);
  async function refresh(cached?:ReturnType<typeof api>) {
    const version=++generation.current;
    try {
      const result=await (cached || api("/api/state"));
      if(version!==generation.current)return;
      live.current=result.mode==="snowflake";setMode(live.current?"snowflake":"local");
      publishState(live.current?result.state:readDemo(window.localStorage));
    } catch(err) {if(version===generation.current)setError(err instanceof Error?err.message:"Could not load your data. Retry.");}
    finally {if(version===generation.current)setReady(true);}
  }
  useEffect(()=> {initialRequest.current ||= api("/api/state");void refresh(initialRequest.current);return ()=>{generation.current++;};},[]);
  function commit(next:DemoState) {
    try {if(!live.current)writeDemo(window.localStorage,next);publishState(next);return true;}
    catch {setError("Your changes couldn’t be saved. Check that browser storage is enabled and has space, then try again.");return false;}
  }
  async function change(work:()=>Promise<boolean>) {
    if(locked.current || !current.current)return false;
    locked.current=true;setPending(true);
    try{return await work();}catch(err){setError(err instanceof Error?err.message:"The change could not be saved.");return false;}
    finally {locked.current=false;setPending(false);}
  }
  const value:DemoContextValue={state,ready,error,mode,pending,resetVersion,refresh,
    async addItem(draft) {return change(async()=> {
      let item:CampusItem;
      if(live.current) {
        const fingerprint=JSON.stringify(draft);
        const key=attempts.current.get(fingerprint) || crypto.randomUUID();attempts.current.set(fingerprint,key);
        const result=await api("/api/items",{draft,key});item=result.item;
        attempts.current.delete(fingerprint);
      } else item={...draft,title:draft.title.trim(),description:draft.description.trim(),location:draft.location.trim(),meetingDetails:draft.meetingDetails.trim(),id:crypto.randomUUID(),demo:false,color:current.current!.items.length%4,createdAt:new Date().toISOString()};
      return commit({...current.current!,items:mergeSearchCards(current.current!.items,[item])});
    });},
    async decide(id,decision) {return change(async()=> {if(live.current)await api("/api/swipes",{id,decision});return commit({...current.current!,decisions:{...current.current!.decisions,[id]:decision}});});},
    async saveProfile(profile) {return change(async()=> {if(live.current)await api("/api/profile",profile);return commit({...current.current!,profile});});},
    async reset() {
      if(!current.current){const next=freshDemo();try{writeDemo(window.localStorage,next);}catch{setError("Browser storage is unavailable.");return false;}await refresh();return true;}
      return change(async()=> {const next=live.current?(await api("/api/reset",{})).state:freshDemo();const saved=commit(next);if(saved)setResetVersion(v=>v+1);return saved;});
    },
    importSearchCards(items){return current.current?commit({...current.current,items:mergeSearchCards(current.current.items,items)}):false;}
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useDemo(){const value=useContext(Context);if(!value)throw new Error("useDemo must be used within DemoProvider");return value;}
