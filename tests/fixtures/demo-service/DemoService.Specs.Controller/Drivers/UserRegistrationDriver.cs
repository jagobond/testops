using DemoService.Specs.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;

namespace DemoService.Specs.Controller.Drivers;

public class UserRegistrationDriver() : ActionAttempt<RegisterInputModel, UserReferenceModel>(registerInput =>
{
    var controller = new UserController();
    return controller.Register(registerInput);
});