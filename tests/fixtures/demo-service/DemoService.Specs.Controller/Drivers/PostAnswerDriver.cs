using DemoService.Specs.Controller.Support;
using DemoService.Specs.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;

namespace DemoService.Specs.Controller.Drivers;

public class PostAnswerDriver(
    QuestionContext questionContext,
    AuthContext authContext,
    QuestionDetailsPageDriver questionDetailsPageDriver)
    : ActionAttempt<AnswerInputModel, AnswerDetailModel>(answerInput =>
    {
        var controller = new QuestionController();
        var result = questionContext.CurrentAnswer = controller
            .PostAnswer(questionContext.CurrentQuestionId, answerInput, authContext.AuthToken);
        questionDetailsPageDriver.LoadPage(questionContext.CurrentQuestionId);
        return result;
    });