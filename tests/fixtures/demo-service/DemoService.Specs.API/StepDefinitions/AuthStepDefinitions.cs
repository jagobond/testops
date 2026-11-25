using AwesomeAssertions;
using DemoService.Specs.API.Drivers;
using DemoService.Specs.API.Support;
using DemoService.Specs.Support;
using DemoService.Web.Models;
using Reqnroll;

namespace DemoService.Specs.API.StepDefinitions;

[Binding]
public class AuthStepDefinitions(AuthContext authContext, AuthApiDriver authApiDriver)
{
    [Given("user Marvin is authenticated")]
    [Given("the user is authenticated")]
    public void GivenTheUserIsAuthenticated()
    {
        authContext.Authenticate(DomainDefaults.UserName, DomainDefaults.UserPassword);
    }

    [Given("the user is not authenticated")]
    public void GivenTheUserIsNotAuthenticated()
    {
        authApiDriver.GetCurrentUser().Should().BeNull();
    }

    [When("the user attempts to log in with user name {string} and password {string}")]
    public void WhenTheUserAttemptsToLogInWithUserNameAndPassword(string userName, string password)
    {
        authApiDriver.Login.Perform(
            new LoginInputModel {Name = userName, Password = password}, true);
    }

    [Then("the login attempt should be successful")]
    public void ThenTheLoginAttemptShouldBeSuccessful()
    {
        authApiDriver.Login.ShouldBeSuccessful();
    }

    [Then("the user should be authenticated")]
    public void ThenTheUserShouldBeAuthenticated()
    {
        var currentUser = authApiDriver.GetCurrentUser();
        currentUser.Should().NotBeNull();
        currentUser.Name.Should().Be(authApiDriver.Login.LastInput.Name);
    }
}