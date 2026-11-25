using DemoService.Specs.Controller.Support;
using DemoService.Specs.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;

namespace DemoService.Specs.Controller.Drivers;

public class AskQuestionDriver(AuthContext authContext) : ActionAttempt<AskInputModel, QuestionSummaryModel>(askInput =>
{
    var controller = new QuestionController();
    return controller.AskQuestion(askInput, authContext.AuthToken);
});