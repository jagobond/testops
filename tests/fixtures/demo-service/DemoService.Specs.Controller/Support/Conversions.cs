using DemoService.Specs.Support;
using DemoService.Web.Models;
using Reqnroll;

namespace DemoService.Specs.Controller.Support;

[Binding]
public class Conversions
{
    [StepArgumentTransformation]
    public AskInputModel ConvertAskInputModel(Table questionTable)
    {
        return questionTable.CreateInstance(DomainDefaults.GetDefaultAskInput);
    }
}