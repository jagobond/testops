using Reqnroll;

namespace DemoService.Specs.WebUI.Support;

[Binding]
public class AppHostingHooks
{
    [AfterTestRun]
    public static void StopApp()
    {
        AppHostingContext.StopApp();
    }
}