using DemoService.Specs.API.Support;
using DemoService.Web.Models;

namespace DemoService.Specs.API.Drivers;

public class HomeApiDriver(WebApiContext webApiContext)
{
    public HomePageModel GetHomePageModel()
    {
        return webApiContext.ExecuteGet<HomePageModel>("/api/home");
    }
}