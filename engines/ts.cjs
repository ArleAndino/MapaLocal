const ts=require('typescript'),fs=require('fs'),path=require('path');
const input=JSON.parse(fs.readFileSync(0,'utf8')),root=input.root;
const normalized=p=>path.resolve(p).replace(/\\/g,'/');
const byPath=new Map(input.files.map(f=>[normalized(path.join(root,f.id)),f]));
let options={target:ts.ScriptTarget.Latest,module:ts.ModuleKind.CommonJS,experimentalDecorators:true,allowJs:true,noEmit:true,skipLibCheck:true};
const config=ts.findConfigFile(root,ts.sys.fileExists);
if(config){const parsed=ts.readConfigFile(config,ts.sys.readFile);if(parsed.config)options={...options,...ts.parseJsonConfigFileContent(parsed.config,ts.sys,path.dirname(config)).options,noEmit:true};}
const host=ts.createCompilerHost(options),originalRead=host.readFile.bind(host);
host.readFile=p=>byPath.has(normalized(p))?byPath.get(normalized(p)).source:originalRead(p);
const program=ts.createProgram([...byPath.keys()],options,host),checker=program.getTypeChecker();
const result={methods:[],calls:[],diagnostics:[],templates:[],http:[]},declarations=new Map();
function pos(sf,n){return sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1;}
function isMethod(n){return ts.isMethodDeclaration(n)||ts.isConstructorDeclaration(n)||ts.isFunctionDeclaration(n)||ts.isArrowFunction(n)||ts.isFunctionExpression(n);}
function methodName(n){return n.name?n.name.getText():ts.isConstructorDeclaration(n)?'constructor':n.parent&&n.parent.name?n.parent.name.getText():'anonymous';}
function owner(n){let p=n.parent;while(p){if(ts.isClassDeclaration(p))return p.name?p.name.text:'';p=p.parent;}return '';}
for(const sf of program.getSourceFiles()){
 const file=byPath.get(normalized(sf.fileName));if(!file)continue;
 for(const d of program.getSyntacticDiagnostics(sf))result.diagnostics.push({file:file.id,line:d.start===undefined?1:sf.getLineAndCharacterOfPosition(d.start).line+1,severity:'error',message:ts.flattenDiagnosticMessageText(d.messageText,' '),engine:'TypeScript'});
 function visit(n){if(isMethod(n)&&n.body){const id=file.id+'::method:'+n.getStart(sf),m={id,file:file.id,name:methodName(n),owner:owner(n),line:pos(sf,n),endLine:sf.getLineAndCharacterOfPosition(n.end).line+1,kind:'method'};declarations.set(n,m);result.methods.push(m);}
  if(ts.isPropertyAssignment(n)&&['templateUrl','template'].includes(n.name.getText())&&ts.isStringLiteralLike(n.initializer)){
   result.templates.push({file:file.id,value:n.initializer.text,inline:n.name.getText()==='template',line:pos(sf,n),owner:owner(n)});
  }ts.forEachChild(n,visit);
 }visit(sf);
}
for(const sf of program.getSourceFiles()){
 const file=byPath.get(normalized(sf.fileName));if(!file)continue;
 function visit(n,current){if(declarations.has(n))current=declarations.get(n);
  if(ts.isThrowStatement(n))result.diagnostics.push({file:file.id,line:pos(sf,n),severity:'warning',message:'throw declarado; no demuestra una excepción durante la ejecución.',engine:'TypeScript'});
  if((ts.isCallExpression(n)||ts.isNewExpression(n))&&current){
   const signature=checker.getResolvedSignature(n),declaration=signature&&signature.declaration,target=declarations.get(declaration);
   result.calls.push({source:current.id,target:target?target.id:null,file:file.id,line:pos(sf,n),expression:n.expression.getText(sf),confidence:target?'resolved':'unresolved'});
   if(ts.isCallExpression(n)&&ts.isPropertyAccessExpression(n.expression)&&['get','post','put','delete','patch','head','options'].includes(n.expression.name.text)&&n.arguments.length&&ts.isStringLiteralLike(n.arguments[0])){
    const receiver=n.expression.expression.getText(sf),type=checker.typeToString(checker.getTypeAtLocation(n.expression.expression));
    if(/http/i.test(receiver)||/HttpClient/.test(type))result.http.push({source:current.id,file:file.id,line:pos(sf,n),verb:n.expression.name.text.toUpperCase(),url:n.arguments[0].text});
   }
  }ts.forEachChild(n,c=>visit(c,current));
 }visit(sf,null);
}
process.stdout.write(JSON.stringify(result));
