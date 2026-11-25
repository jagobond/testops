using System;
using DemoService.Specs.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;

namespace DemoService.Specs.Controller.Drivers;

public class LoginDriver : ActionAttempt<LoginInputModel, string>
{
    public event Action<LoginInputModel, string> OnAuthenticated;
        
    protected override string DoAction(LoginInputModel loginInput)
    {
        var controller = new AuthController();
        var authToken = controller.Login(new LoginInputModel { Name = loginInput.Name, Password = loginInput.Password });
        OnAuthenticated?.Invoke(loginInput, authToken);
        return authToken;
    }
}