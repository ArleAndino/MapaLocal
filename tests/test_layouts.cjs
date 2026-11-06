const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const base=path.join(__dirname,'..','static');
const context={Map,Set,Math};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(base,'layouts.js'),'utf8'),context);
const nodes=[{id:'low',neighbors:1,folder:'a',language:'C#'},{id:'high',neighbors:10,folder:'a',language:'C#'},
 {id:'mid',neighbors:4,folder:'a',language:'C#'},{id:'other',neighbors:0,folder:'b',language:'TypeScript'}];
const positions=context.gravityPositions(nodes);
assert(positions.get('low').y<positions.get('mid').y);assert(positions.get('mid').y<positions.get('high').y);
assert.equal(positions.size,4);assert.notEqual(positions.get('other').x,positions.get('low').x);
const events=[],queue=[],worker={self:{postMessage:m=>events.push(m)},setTimeout:f=>{queue.push(f);return 1;},clearTimeout:()=>{},Map,Math};vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(base,'layout-worker.js'),'utf8'),worker);
assert(worker.targetDistance(9)<worker.targetDistance(1));
worker.self.onmessage({data:{type:'start',nodes:[{id:'a',x:0,y:0,fixed:true},{id:'b',x:600,y:0}],edges:[{source:'a',target:'b',weight:9}]}});
while(queue.length)queue.shift()();
const result=new Map(events[events.length-1].positions);
assert.equal(result.get('a').x,0);assert(Math.abs(result.get('b').x)<600);assert(Number.isFinite(result.get('b').y));assert(events[events.length-1].done);
console.log('Layout tests passed: ordering, groups, magnetic distance, convergence and pinning.');
