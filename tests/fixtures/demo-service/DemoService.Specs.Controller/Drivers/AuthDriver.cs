using System.Net;
using DemoService.Specs.Controller.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;
using DemoService.Web.Utils;

namespace DemoService.Specs.Controller.Drivers;

public class AuthDriver(LoginDriver login, AuthContext authContext)
{
    public LoginDriver Login { get; } = login;

    public UserReferenceModel GetCurrentUser()
    {
        var controller = new AuthController();
        try
        {
            return controller.GetCurrentUser(authContext.AuthToken);
        }
        catch (HttpResponseException e) when (e.StatusCode == HttpStatusCode.NotFound)
        {
            return null;
        }
    }
}