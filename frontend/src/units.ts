export type Units='metric'|'imperial';
export const KG_PER_LB=0.45359237;
export function displayWeight(kg:number,units:Units){return units==='imperial'?kg/KG_PER_LB:kg;}
export function storedWeight(value:number,units:Units){return units==='imperial'?value*KG_PER_LB:value;}
export function weightLabel(kg:number,units:Units){return `${displayWeight(kg,units).toFixed(1)} ${units==='imperial'?'lb':'kg'}`;}
export function heightLabel(cm:number,units:Units){return units==='imperial'?`${(cm/2.54).toFixed(1)} in`:`${cm.toFixed(1)} cm`;}
