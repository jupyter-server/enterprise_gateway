/*
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

name := "toree-launcher"

version := sys.props.getOrElse("version", default = "1.0").replaceAll("dev[0-9]", "SNAPSHOT")

scalaVersion := "2.11.12"

resolvers += "Typesafe Repo" at "https://repo.typesafe.com/typesafe/releases/"
/* resolvers += "Sonatype Repository" at "https://oss.sonatype.org/content/repositories/releases/" */
resolvers += "Sonatype Maven Central Mirror" at "https://maven-central.storage-download.googleapis.com/maven2/"

libraryDependencies += "com.typesafe.play" %% "play-json" % "2.3.10" // Apache v2
libraryDependencies += "org.apache.toree" % "toree-assembly" % "0.4.0-incubating" /*from "https://archive.apache.org/dist/incubator/toree/0.4.0-incubating/toree/toree-assembly-0.4.0-incubating.jar"*/
