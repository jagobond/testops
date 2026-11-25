using System;
using System.Net;
using AwesomeAssertions;
using DemoService.Specs.API.Support;
using DemoService.Web.Models;
using DemoService.Specs.Support;
using DemoService.Web.Utils;

namespace DemoService.Specs.API.Drivers;

public class AuthApiDriver(WebApiContext webApiContext, AuthApiDriver.LoginDriver login)
{
    public class LoginDriver(WebApiContext webApiContext) : ActionAttempt<LoginInputModel, string>
    {
        public event Action<LoginInputModel, string> OnAuthenticated;

        protected override string DoAction(LoginInputModel loginInput)
        {
            var response = webApiContext.ExecutePost<string>("api/auth", loginInput);
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            var authToken = response.ResponseData;
            OnAuthenticated?.Invoke(loginInput, authToken);
            return authToken;
        }
    }

    public LoginDriver Login { get; } = login;

    public UserReferenceModel GetCurrentUser()
    {
        try
        {
            return webApiContext.ExecuteGet<UserReferenceModel>("/api/auth");
        }
        catch (HttpResponseException e) when (e.StatusCode == HttpStatusCode.NotFound)
        {
            return null;
        }
    }
}