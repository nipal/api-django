import React from "react";
import { hot } from "react-hot-loader";
import PropTypes from "prop-types";
import InputGroup from "@agir/lib/bootstrap/InputGroup";
import { displayNumber, displayPrice } from "@agir/lib/utils/display";
import styled from "styled-components";

import "./style.css";

const DEFAULT_AMOUNTS = [100, 50, 25, 15, 10];

const AmountButton = styled.button`
  display: block;
  width: 30%;
  height: 50px;
  margin: 10px 0;
  font-weight: bold;
  min-width: 200px;
`;

function numberValue(s) {
  return parseFloat(s.replace(/,/, "."));
}

class AmountWidget extends React.Component {
  constructor(props) {
    super();

    const amountChoices = props.amountChoices || DEFAULT_AMOUNTS;

    const custom = props.amount && !amountChoices.includes(props.amount);
    const customText = custom ? displayNumber(props.amount, 2) : "";

    this.state = {
      custom,
      customText
    };
  }

  updateWithButton(value) {
    this.setState({ custom: false, customText: "" });
    this.props.onAmountChange(value);
  }

  updateWithCustomValue(s) {
    if (s === "") {
      this.setState({ custom: false });
      this.props.onAmountChange(null);
      return;
    }

    const m = s.match(/^([0-9]+)(?:(,[0-9]*))?$/);

    if (m !== null) {
      const newText = m[1] + (m[2] || "").slice(0, 3);
      const value = numberValue(newText);
      this.setState({ custom: true, customText: newText });
      this.props.onAmountChange(value);
    }
  }

  render() {
    const { custom, customText } = this.state;
    const { amount, error, showTaxCredit } = this.props;

    const amountChoices = this.props.amountChoices || DEFAULT_AMOUNTS;

    return (
      <div className="amount-component">
        <div className={`form-group${error ? " has-error" : ""}`}>
          <input type="hidden" value={amount ? amount : ""} name="amount" />
          {amountChoices.map(value => (
            <AmountButton
              key={value}
              type="button"
              onClick={() => this.updateWithButton(value)}
              className={[
                "btn",
                custom || amount !== value ? "btn-default" : "btn-primary"
              ].join(" ")}
            >
              {value}&nbsp;€
            </AmountButton>
          ))}
          <InputGroup>
            <input
              type="text"
              className="form-control"
              placeholder="autre montant"
              step={1}
              onChange={e => this.updateWithCustomValue(e.target.value)}
              value={
                numberValue(customText) === amount
                  ? customText
                  : custom
                  ? displayNumber(amount, 2)
                  : ""
              }
            />
            <InputGroup.Addon>€</InputGroup.Addon>
          </InputGroup>

          {error && <span className="help-block">{error}</span>}
        </div>
        <p>
          {showTaxCredit &&
            (amount ? (
              <em>
                Si je paye des impôts, après réduction, ma contribution nette
                sera de seulement{" "}
                <strong className="text-danger">
                  {displayPrice(amount * 0.34)}
                </strong>
                &nbsp;!
              </em>
            ) : (
              <em>
                Si je paye des impôts, je profite d&apos;une réduction
                d&apos;impôt de <strong>66&nbsp;%</strong> de la somme donnée !
              </em>
            ))}
        </p>
      </div>
    );
  }
}

AmountWidget.propTypes = {
  amount: PropTypes.number,
  onAmountChange: PropTypes.func,
  error: PropTypes.string,
  amountChoices: PropTypes.array,
  showTaxCredit: PropTypes.bool
};

export default hot(module)(AmountWidget);
