#!/usr/bin/env python3
import os
import sys
import json
import tensorflow as tf
from train_script import parse_arguments, main


def progressive_train_parse_arguments(argv):
    import argparse

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--progressive_epochs", type=int, nargs="+", help="progressive epochs")
    parser.add_argument("--progressive_batch_sizes", type=int, nargs="*", help="progressive batch sizes")
    parser.add_argument("--progressive_input_shapes", type=int, nargs="*", help="progressive input shapes")
    parser.add_argument("--progressive_dropouts", type=float, nargs="*", help="progressive dropouts")
    parser.add_argument("--progressive_drop_connect_rates", type=float, nargs="*", help="progressive drop_connect_rates")
    parser.add_argument("--progressive_magnitudes", type=int, nargs="*", help="progressive magnitudes")
    parser.add_argument("--progressive_mixup_alphas", type=float, nargs="*", help="progressive mixup alphas")
    parser.add_argument("--progressive_cutmix_alphas", type=float, nargs="*", help="progressive cutmix alphas")
    parser.add_argument("--reuse_optimizer", action="store_true", help="reuse optimizer")
    if "-h" in argv or "--help" in argv:
        parser.print_help()
        print("")
        print(">>>> train_script.py arguments:")
        parse_arguments(argv)
    progressive_args, train_argv = parser.parse_known_args(argv)
    train_args = parse_arguments(train_argv)
    return progressive_args, train_args


if __name__ == "__main__":
    progressive_args, train_args = progressive_train_parse_arguments(sys.argv[1:])
    print(">>>> Progressive args:", progressive_args)

    initial_epoch = train_args.initial_epoch
    progressive_epochs = progressive_args.progressive_epochs
    init_stage = sum([initial_epoch >= ii for ii in progressive_epochs])
    get_stage_param = lambda params, stage, default: (params[stage] if len(params) > stage + 1 else params[-1]) if params else default
    cyan_print = lambda ss: print("\033[1;36m" + ss + "\033[0m")

    for stage in range(init_stage, len(progressive_epochs)):
        train_args.epochs = progressive_epochs[stage]
        train_args.input_shape = get_stage_param(progressive_args.progressive_input_shapes, stage, train_args.input_shape)
        train_args.batch_size = get_stage_param(progressive_args.progressive_batch_sizes, stage, train_args.batch_size)
        train_args.magnitude = get_stage_param(progressive_args.progressive_magnitudes, stage, train_args.magnitude)
        train_args.mixup_alpha = get_stage_param(progressive_args.progressive_mixup_alphas, stage, train_args.mixup_alpha)
        train_args.cutmix_alpha = get_stage_param(progressive_args.progressive_cutmix_alphas, stage, train_args.cutmix_alpha)

        dropout = get_stage_param(progressive_args.progressive_dropouts, stage, None)
        drop_connect_rate = get_stage_param(progressive_args.progressive_drop_connect_rates, stage, None)
        if dropout is not None or drop_connect_rate is not None:
            additional_model_kwargs = json.loads(train_args.additional_model_kwargs) if train_args.additional_model_kwargs else {}
            if dropout is not None:
                additional_model_kwargs.update({"dropout": dropout})
            if drop_connect_rate is not None:
                additional_model_kwargs.update({"drop_connect_rate": drop_connect_rate})
            train_args.additional_model_kwargs = json.dumps(additional_model_kwargs)

        print("")
        cyan_print(
            ">>>> [Stage {}] epochs: {}, batch_size: {}, input_shape: {}, magnitude: {}, dropout: {}".format(
                stage, train_args.epochs, train_args.batch_size, train_args.input_shape, train_args.magnitude, dropout
            )
        )
        model, _ = main(train_args)

        train_args.initial_epoch += progressive_epochs[stage]
        train_args.restore_path = None
        train_args.pretrained = train_args.basic_save_name + "_latest.h5"  # Build model and load weights
        if progressive_args.reuse_optimizer:
            train_args.optimizer = model.optimizer