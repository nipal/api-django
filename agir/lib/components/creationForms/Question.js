import React from "react";
import PropTypes from "prop-types";

const Question = ({ question, value, setValue }) => (
  <div>
    <h4>{question.question}</h4>
    <label className="radio-inline">
      <input
        type="radio"
        name={question.id}
        onChange={() => setValue(true)}
        checked={value === true}
      />{" "}
      Oui{" "}
    </label>
    <label className="radio-inline">
      {" "}
      <input
        type="radio"
        name={question.id}
        onChange={() => setValue(false)}
        checked={value === false}
      />{" "}
      Non{" "}
    </label>
  </div>
);
Question.propTypes = {
  question: PropTypes.object,
  value: PropTypes.bool,
  setValue: PropTypes.func
};

export default Question;
