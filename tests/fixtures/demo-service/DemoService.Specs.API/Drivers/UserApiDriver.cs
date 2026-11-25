using DemoService.Specs.API.Support;
using DemoService.Specs.Support;
using DemoService.Web.Models;

namespace DemoService.Specs.API.Drivers;

public class UserApiDriver
{
    public ActionAttempt<RegisterInputModel, UserReferenceModel> Register { get; }

    public UserApiDriver(WebApiContext webApiContext, ActionAttemptFactory actionAttemptFactory)
    {
        Register = actionAttemptFactory.CreateWithStatusCheck<RegisterInputModel, UserReferenceModel>(
            nameof(Register),
            registerInput => webApiContext.ExecutePost<UserReferenceModel>("/api/user", registerInput));
    }
}