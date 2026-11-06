using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

var input = JsonDocument.Parse(Console.In.ReadToEnd()).RootElement;
var trees = input.GetProperty("files").EnumerateArray().Select(f => CSharpSyntaxTree.ParseText(f.GetProperty("source").GetString()!, path:f.GetProperty("id").GetString()!)).ToArray();
var references = ((string?)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") ?? "").Split(Path.PathSeparator).Where(File.Exists).Select(p => MetadataReference.CreateFromFile(p));
var compilation = CSharpCompilation.Create("LocalIndex", trees, references, new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
var methods = new List<object>(); var calls = new List<object>(); var diagnostics = new List<object>(); var endpoints = new List<object>();
var methodIds = new Dictionary<(string,int),string>();
int Line(SyntaxNode n) => n.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
string? Literal(AttributeSyntax a) => a.ArgumentList?.Arguments.FirstOrDefault()?.Expression is LiteralExpressionSyntax l && l.IsKind(SyntaxKind.StringLiteralExpression) ? l.Token.ValueText : null;
string AttributeName(AttributeSyntax a) => a.Name.ToString().Split('.').Last().Replace("Attribute", "");
foreach(var tree in trees) {
 foreach(var d in tree.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error)) diagnostics.Add(new {file=tree.FilePath,line=d.Location.GetLineSpan().StartLinePosition.Line+1,severity="error",message=d.GetMessage(),engine="Roslyn"});
 foreach(var n in tree.GetRoot().DescendantNodes().Where(n => n is BaseMethodDeclarationSyntax || n is LocalFunctionStatementSyntax)) {
  string name = n switch {MethodDeclarationSyntax m => m.Identifier.Text, ConstructorDeclarationSyntax c => c.Identifier.Text,LocalFunctionStatementSyntax f => f.Identifier.Text,_=>n.Kind().ToString()};
  var type=n.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault();
  var id=tree.FilePath+"::method:"+n.SpanStart;methodIds[(tree.FilePath,n.SpanStart)]=id;
  methods.Add(new {id,file=tree.FilePath,name,owner=type?.Identifier.Text??"",line=Line(n),endLine=n.GetLocation().GetLineSpan().EndLinePosition.Line+1,kind="method"});
  if(n is MethodDeclarationSyntax method) {
   var prefix=type?.AttributeLists.SelectMany(l=>l.Attributes).Where(a=>AttributeName(a)=="Route").Select(Literal).FirstOrDefault()??"";
   var route=method.AttributeLists.SelectMany(l=>l.Attributes).Where(a=>AttributeName(a)=="Route").Select(Literal).FirstOrDefault();
   foreach(var attr in method.AttributeLists.SelectMany(l=>l.Attributes).Where(a=>new[]{"HttpGet","HttpPost","HttpPut","HttpDelete","HttpPatch","HttpHead","HttpOptions"}.Contains(AttributeName(a)))) {
    var suffix=Literal(attr)??route??"";
    var url=suffix.StartsWith("/")||suffix.StartsWith("~/")?suffix.TrimStart('~'):(prefix.TrimEnd('/')+"/"+suffix.TrimStart('/'));
    url=url.Replace("[controller]",(type?.Identifier.Text??"").Replace("Controller", "")).Replace("[action]",name);
    endpoints.Add(new {target=id,file=tree.FilePath,line=Line(method),verb=AttributeName(attr).Substring(4).ToUpperInvariant(),url});
   }
  }
 }
}
foreach(var tree in trees) {
 var model=compilation.GetSemanticModel(tree);
 foreach(var n in tree.GetRoot().DescendantNodes()) {
  if(n is ThrowStatementSyntax || n is ThrowExpressionSyntax) diagnostics.Add(new {file=tree.FilePath,line=Line(n),severity="warning",message="throw declarado; no demuestra una excepción durante la ejecución.",engine="Roslyn"});
  if(n is not InvocationExpressionSyntax && n is not ObjectCreationExpressionSyntax)continue;
  var caller=n.Ancestors().FirstOrDefault(a=>methodIds.ContainsKey((tree.FilePath,a.SpanStart)));if(caller==null)continue;
  var symbol=model.GetSymbolInfo(n).Symbol as IMethodSymbol;
  var declaration=symbol?.OriginalDefinition.DeclaringSyntaxReferences.FirstOrDefault();string? target=null;
  if(declaration!=null)methodIds.TryGetValue((declaration.SyntaxTree.FilePath,declaration.Span.Start),out target);
  calls.Add(new {source=methodIds[(tree.FilePath,caller.SpanStart)],target,file=tree.FilePath,line=Line(n),expression=n is InvocationExpressionSyntax call?call.Expression.ToString():n.ToString(),confidence=target!=null?"resolved":"unresolved"});
 }
}
Console.Write(JsonSerializer.Serialize(new {methods,calls,diagnostics,endpoints}));
